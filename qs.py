# Instead of using the hostname, get the IPv4 address
import socket
hostname = "db.xltjimtqikfgfacryyef.supabase.co"
ipv4_address = socket.gethostbyname(hostname)

# Use the IPv4 address in your connection string
DATABASE_URL = f"postgresql://username:password@{ipv4_address}:5432/postgres"