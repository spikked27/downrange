"""Local administrator recovery: python -m app.reset_password (interactive)."""
import getpass
from .config import Settings
from .store import Store
from .security import password_hash

def main():
    settings=Settings(); store=Store(settings.data_dir/"downrange.sqlite3")
    password=getpass.getpass("New admin password (12+ characters): ")
    again=getpass.getpass("Repeat new password: ")
    if password!=again or not 12<=len(password)<=128:
        raise SystemExit("Passwords must match and contain 12–128 characters")
    user=store.one("SELECT id FROM users WHERE username='admin' AND admin=1")
    if not user: raise SystemExit("Administrator account not found")
    with store.connect() as c:
        c.execute("UPDATE users SET password=? WHERE id=?",(password_hash(password),user["id"]))
        c.execute("DELETE FROM sessions WHERE user_id=?",(user["id"],))
    print("Password changed; previous administrator sessions revoked.")
if __name__=="__main__": main()
