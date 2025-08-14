from ldap3 import Server, Connection, NTLM, ALL

server_url = "ldap://18.179.202.159:389"
netbios = "TESTADDS"          # NetBIOS
username = "000000"
password = "000000"
upn = f"{username}@testadds.internal"

srv = Server(server_url, get_info=ALL)

def test(label, user, auth=None):
    c = Connection(srv, user=user, password=password,
                   authentication=auth if auth else 'SIMPLE',
                   raise_exceptions=False)
    ok = c.bind()
    print(f"[{label}] ok={ok} last_error={c.last_error} result={c.result}")
    c.unbind()

test("NTLM", f"{netbios}\\{username}", NTLM)
test("SIMPLE-UPN", upn)
# DN 直指定例 (分かっている場合):
# test("SIMPLE-DN", "CN=000000,OU=Users,DC=testadds,DC=internal")
