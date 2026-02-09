import nmap

nm = nmap.PortScanner()
target_ip = "192.168.1.14"

nm.scan(target_ip, arguments='-p 135,445 -sT')

for port in [135, 445]:
    state = nm[target_ip]['tcp'][port]['state']
    print(f"Port {port} is {state}")
