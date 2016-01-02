import sqlite3 as lite
import time
import logging


class Database:

    def __init__(self,first_run, db_file):

        self.dbPath = db_file
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        fh = logging.FileHandler('output.log')
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.addHandler(fh)
        self.logger = logger
        self.con = None
        self.getConnection()
        self.keys = ["app_name", "replaces_id", "app_icon", "summary",
                     "body", "actions", "hints", "expire_timeout"]
        # try:
        #     cur = self.con.cursor()
        #     cur.execute("select * from notifications")
        # except Exception:
        #     self.first_run()
        if (first_run):
            self.first_run()


    def first_run(self):
        cur = self.con.cursor()
        cur.executescript("""
        DROP TABLE IF EXISTS notifications;
        DROP TABLE IF EXISTS feedbacks;
        CREATE TABLE notifications(body TEXT,app_name TEXT,summary TEXT,window TEXT,timestamp INT);
        CREATE TABLE feedbacks(app_name TEXT,accept INT,reject INT);
        """)
        self.con.commit()
        self.con.close()
        self.con = None


    def getConnection(self):
        try:
            self.con = lite.connect(self.dbPath)
            #self.logger.debug("connection to database created")
        except lite.Error, e:
            self.logger.debug("Error connecting to Db : %s:" % e.args[0])



    def save_notification(self, notification, window):
        self.getConnection()
        #self.logger.debug("Inserting notification details in the DB ")
        app_name , body, summary = ("","","")
        #I tried 10 things and neither worked so screw it:
        cur = self.con.cursor()
        if "app_name" in notification:
            app_name = notification["app_name"]
        elif "body" in notification:
            body = notification["body"]
        elif "summary" in notification:
            summary = notification["summary"]
        timestamp = time.time()
        vals = (app_name,body,summary,window,int(timestamp))
        try:
            cur.execute("INSERT INTO notifications VALUES(?,?,?,?,?)", vals)
            self.logger.debug("Notification successfully inserted to DB")
            self.con.commit()
            self.con.close()
        except Exception, e:
            self.logger.debug("Insertion of new notification failed with %s" % e.args[0])



    def persist_feedback(self,app_name, feedback_index):
        self.getConnection()
        cur = self.con.cursor()
        try:
            cur.execute("select * from feedbacks WHERE app_name=?", (app_name,))
        except Exception, e:
            self.logger.debug("Database read failed with %s" % e.args[0])
        res = cur.fetchone()
        try:
            if res is not None:
                if feedback_index == 0:
                    #ACCEPT
                    result = int(res[1]) + 1
                    cur.execute("update feedbacks SET accept=? WHERE app_name=?", (result, app_name))
                if feedback_index == 1:
                    #REJECT
                    result = res[feedback_index] + 1
                    cur.execute("update feedbacks SET reject=? WHERE app_name=?", (result, app_name))
            else:
                if feedback_index == 0:
                    #ACCEPT
                    result = 1
                    cur.execute("INSERT INTO feedbacks VALUES(?,?,?)", (app_name, result, 0))
                if feedback_index == 1:
                    #REJECT
                    result = 1
                    cur.execute("INSERT INTO feedbacks VALUES(?,?,?)", (app_name, 0, result))
                self.logger.debug("Feedback inserted for notification from: %s" %app_name)
            self.con.commit()
            self.con.close()
        except Exception, e:
            self.logger.debug("Inserting feedback failed with: %s" % e.args[0])

    def get_window_feedback(self, window):
        if window == "":
            return []
        self.getConnection()
        cur = self.con.cursor()
        try:
            cur.execute("SELECT * from feedbacks WHERE app_name=?", (window,))
            result = cur.fetchone()
            if result is not None:
                self.logger.debug("Feedback list successfully read for app name %s as: %s", window, str(result))
                return [result[1], result[2]]
            else:
                return []
        except Exception, e:
            self.logger.debug("Reading feedback failed with: %s" % e.args[0])
            return []

