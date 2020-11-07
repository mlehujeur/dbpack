import sqlite3, os
from _sqlite3 import OperationalError
import sys, traceback
import numpy as np
from dbtools.printcolors import printyellow, printblue
from dbtools.sqlite_functions import divrest, substring


class NoTransactionOpen(OperationalError):
    pass


class TransactionAlreadyOpen(OperationalError):
    pass


class TransactionFailed(OperationalError):
    pass


class EmptySelection(OperationalError):
    pass


def error_message():
    type, value, trace = sys.exc_info()
    message = "".join(traceback.format_exception(type, value, trace, limit=10))
    return message


SQLITE_EXEC_ERROR_MESSAGE = """could not execute the sqlite command below : 
****** BEGIN OF SQLITE COMMAND
{sqlite_command}
****** END OF SQLITE COMMAND
error :
{error_message}"""

printer = printyellow


class Database(object):

    def __init__(self, sqlite_file, create=False, verbose=True, timeout=120.):

        if not create:
            if not os.path.isfile(sqlite_file):
                raise OSError("{} not found, use create=True".format(sqlite_file))

        self.sqlite_file = sqlite_file
        self.connection = None
        self.verbose = verbose
        self.timeout = timeout
        self.transaction = False
        self.subtransaction = False  # for save points

    def __enter__(self):
        """enter the contextual environment (with), the connection is really open here, not in __init__"""
        if self.verbose:
            printer("connecting to : {}".format(self.sqlite_file))

        self.connection = sqlite3.connect(self.sqlite_file, timeout=self.timeout)
        self.connection.isolation_level = None
        self.cursor = self.connection.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON;")  # !!!
        return self

    def __exit__(self, tpe, value, trace):
        self.close()

    def close(self):
        if self.transaction:
            msg = '''you are trying to close a transacting database ({})
                please chose : 
                1   : commit and close
                2   : rollback since last savepoint and close
                3   : rollback since begin transaction and close'''.format(self.sqlite_file)
            msg = "\n".join([s.strip() for s in msg.split('\n')])

            printer(msg)

            choice = input('?')
            while not choice in ["1", "2", "3"]:
                choice = input('?')

            if choice == "1":
                self.commit()
            elif choice == "2":
                self.rollback(raise_an_error=False, ignore_savepoint=False)
            elif choice == "3":
                self.rollback(raise_an_error=False, ignore_savepoint=True)

        if self.verbose:
            printer("closing : {}".format(self.sqlite_file))
            
        self.cursor.close()
        self.connection.close()

    def create_function(self):
        """
        create convenient functions to use in sqlite commands
        LOG : compute the natural logarithm of a number,
              select LOG(COLUMN) from TABLE -> returns the logarithm of COLUMN
        SUBSTRING : isolate sub-string between indexs i (included) and j (excluded)
              select SUBSTRING(COLUMN, 3, 4) -> returns COLUMN[3:4] (python indexation convention)
              select SUBSTRING(COLUMN, 3, 3) -> returns COLUMN[3] (python indexation convention)
        DIVREST : return the rest of the Euclidian division
              select DIVREST(COLUMN, 12.) -> returns COLUMN % 12.
        """
        # compute the natural logarithm
        self.connection.create_function("LOG", 1, np.log)
        self.connection.create_function("SUBSTRING", 3, substring)
        self.connection.create_function("DIVREST", 2, divrest)

    def begin_transaction(self):
        if self.transaction:
            raise TransactionAlreadyOpen()
        if self.verbose:
            printer("starting transaction : {}".format(self.sqlite_file))
        self.cursor.execute('begin transaction')
        self.transaction = True

    def savepoint(self):
        if not self.transaction:
            raise NoTransactionOpen()

        if self.verbose:
            printer("savepoint : {}".format(self.sqlite_file))

        if self.subtransaction:
            # release old save point and start a new one
            self.cursor.execute('RELEASE SAVEPOINT LASTSP')
            self.cursor.execute('SAVEPOINT LASTSP')
        else:
            # start a new savepoint
            self.cursor.execute('SAVEPOINT LASTSP')

        self.subtransaction = True

    def restart_transaction(self):
        """like savepoint except that uncommited modifications will be physically commited,
        this might be used if other connections are waiting for their turn to access the database (use timeout >> 1)
        other connection may see the commited changes"""
        if not self.transaction:
            raise NoTransactionOpen()

        # switch verbose off temporarilly
        verbose = self.verbose
        self.verbose = False
        try:
            self.commit()
            self.begin_transaction()
        finally:
            self.verbose = verbose

        if self.verbose:
            printer("restart transaction  : {}".format(self.sqlite_file))

    def rollback(self, raise_an_error=True, ignore_savepoint=False):
        if not self.transaction:
            raise NoTransactionOpen()

        if self.subtransaction and not ignore_savepoint:
            if self.verbose:
                printer("rolling back : to last savepoint, {}".format(self.sqlite_file))
            self.connection.execute('''rollback transaction to savepoint LASTSP''')
            self.subtransaction = False
            self.connection.commit()
            self.transaction = False
        else:
            if self.verbose:
                printer("rolling back : to begin transaction, {}".format(self.sqlite_file))
            self.connection.rollback()
            self.transaction = False

        if raise_an_error:
            raise TransactionFailed(error_message())

    def commit(self):
        if self.verbose:
            printer("commiting : {}".format(self.sqlite_file))

        if not self.transaction:
            raise NoTransactionOpen()

        if self.subtransaction:
            self.cursor.execute('RELEASE SAVEPOINT LASTSP')
            self.subtransaction = False

        self.connection.commit()
        self.transaction = False

    def execute(self, *args, **kwargs):
        self.cursor.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        self.cursor.executemany(*args, **kwargs)

    @staticmethod
    def _selection_generator(item0, selection, cursortmp):
        try:
            yield item0
            for item in selection:
                yield item
        finally:
            try:
                cursortmp.close()
            except sqlite3.ProgrammingError:
                # if the data base has been closed
                pass

    def select(self, sqlite_command, tup=None):

        cursortmp = self.connection.cursor()
        try:
            if tup is not None:
                selection = cursortmp.execute(sqlite_command, tup)
            else:
                selection = cursortmp.execute(sqlite_command)

            item0 = selection.fetchone()

            if item0 is None:
                if self.verbose:
                    printer('no output for selection\n{}'.format(sqlite_command))
                return None

            return self._selection_generator(item0, selection, cursortmp)

        except (KeyboardInterrupt, OperationalError, Exception) as e:
            error_message = SQLITE_EXEC_ERROR_MESSAGE.format(
                sqlite_command=sqlite_command,
                error_message=str(e))

            e.args = (error_message,)
            raise e  # Exception(error_message)

    def selectscalar(self, sqlite_command, tup=None):
        """
        :param args:
        :param kwargs:
        :return:
        """
        cursortmp = self.connection.cursor()
        try:
            if tup is not None:
                selection = cursortmp.execute(sqlite_command, tup)
            else:
                selection = cursortmp.execute(sqlite_command)

            item0 = selection.fetchone()
            selection.close()

        finally:
            cursortmp.close()

        if item0 is None:
            return None

        value = item0[0]  # because fetchone will return (value, )
        return value

    def select2array(self, cmd, dtype, tup=None):
        """
        extract a column of data and store it into a numpy.array before returning
        the selection must select only one single column
        :param cmd: string, sqlite selection command, must isolate one and only one column
            e.g. ' select NAME from TABLE where NAME LIKE "A%" '
        :param dtype: datatype to use for building the numpy array
        :param tup: see self.select
        :return: numpy.array
        """
        s = self.select(sqlite_command=cmd, tup=tup)
        if s is None:
            return np.asarray([], dtype=dtype)
        return np.asarray([_[0] for _ in list(s)], dtype=dtype)

    def select2arrays(self, cmd, dtypes, tup=None):
        """
        convert selection output to arrays with desired types
        :param cmd: sqlite selection string
        :param dtypes: tuple of types, one per output column
        :param tup: tuple of arguments to pass to self.select (if cmd has ? in it)
        """
        s = self.select(sqlite_command=cmd, tup=tup)
        if s is None:
            return [np.asarray([], dtype=dtype) for dtype in dtypes]

        return [np.asarray(item, dtype) for item, dtype in zip(zip(*list(s)), dtypes)]

    def table_list(self):
        """ list the tables in the database"""
        tables = list(self.select2array('''
            select NAME from sqlite_master 
            where upper(type)="TABLE"
            and upper(NAME) != "SQLITE_SEQUENCE"
            ''', str))

        return tables


if __name__ == '__main__':
    with Database('./tester.sqlite', create=True) as db:
        db.execute('''
            drop table if exists TESTER
            ''')
        db.execute('''
            create table TESTER (
                I     integer primary key autoincrement not null,
                A     real not null)
        ''')

        db.begin_transaction()
        try:

            db.executemany('insert into TESTER (A) values (?)',
                           tuple([(float(_),) for _ in np.arange(10)])
                           )
            db.commit()
        except OperationalError:
            db.rollback(raise_an_error=True)

        print(db.selectscalar('select I from TESTER where I = 3 limit 1'))
        # print(list(db.select('select A from TESTER where A > 2')))
        # s = db.select2array('select A from TESTER where A > 2', int)
        i, a = db.select2arrays('select I, A from TESTER where A > 2', (int, float))
        # print(i)
        # print(a)
