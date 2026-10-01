// Test profile: sideload the add-on, no first-run UI, and two POP3 accounts
// (never contacted; the sandbox has no network) plus Local Folders.
user_pref("extensions.autoDisableScopes", 0);
user_pref("extensions.enabledScopes", 15);
user_pref("xpinstall.signatures.required", false);
user_pref("mail.provider.suppress_dialog_on_startup", true);
user_pref("mail.shell.checkDefaultClient", false);
user_pref("mail.rights.version", 1);
user_pref("app.update.enabled", false);
user_pref("app.update.disabledForTesting", true);

user_pref("mail.accountmanager.accounts", "account1,account2,account3");
user_pref("mail.accountmanager.defaultaccount", "account2");
user_pref("mail.accountmanager.localfoldersserver", "server1");

user_pref("mail.account.account1.server", "server1");
user_pref("mail.server.server1.type", "none");
user_pref("mail.server.server1.hostname", "Local Folders");
user_pref("mail.server.server1.userName", "nobody");
user_pref("mail.server.server1.name", "Local Folders");

user_pref("mail.account.account2.server", "server2");
user_pref("mail.account.account2.identities", "id1");
user_pref("mail.server.server2.type", "pop3");
user_pref("mail.server.server2.hostname", "pop.work.invalid");
user_pref("mail.server.server2.userName", "work");
user_pref("mail.server.server2.name", "Work");
user_pref("mail.server.server2.login_at_startup", false);
user_pref("mail.server.server2.check_new_mail", false);
user_pref("mail.identity.id1.useremail", "work@example.com");
user_pref("mail.identity.id1.fullName", "Test Work");

user_pref("mail.account.account3.server", "server3");
user_pref("mail.account.account3.identities", "id2");
user_pref("mail.server.server3.type", "pop3");
user_pref("mail.server.server3.hostname", "pop.personal.invalid");
user_pref("mail.server.server3.userName", "personal");
user_pref("mail.server.server3.name", "Personal");
user_pref("mail.server.server3.login_at_startup", false);
user_pref("mail.server.server3.check_new_mail", false);
user_pref("mail.identity.id2.useremail", "personal@example.com");
user_pref("mail.identity.id2.fullName", "Test Personal");
