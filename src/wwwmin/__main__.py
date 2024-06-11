from . import server, database


def main():
    db = database.Database(
        uri="db.sqlite3", tables={database.ContactFormSubmission, database.User}
    )
    db.db()
    server.serve()


if __name__ == "__main__":
    main()
