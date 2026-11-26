// ============================================================================
// Device detection on the shop PC.
//
//   * printers installed in Windows / CUPS (USB printers appear here too), with
//     their state, port and a guess of what they are (receipt, label, office,
//     virtual such as "Microsoft Print to PDF");
//   * network printers: every address of the PC's local network (/24) that
//     answers on the raw printing port 9100 — nothing is sent to them;
//   * serial / USB ports a printer or a customer display can be wired to
//     (COM ports on Windows, /dev/usb/lp*, /dev/ttyUSB*… elsewhere).
//
// Barcode scanners are keyboards for the computer: they cannot be listed, they
// are tested by scanning (CMS side).
// ============================================================================

use serde::Serialize;
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream, UdpSocket};
use std::sync::{Arc, Mutex};
use std::time::Duration;

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct DetectedPrinter {
    pub name: String,
    pub system_name: String,
    pub is_default: bool,
    /// ready | offline | paused | printing | unknown
    pub state: String,
    /// receipt | label | office | virtual
    pub kind: String,
    pub port_name: String,
    pub driver_name: String,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct NetworkPrinter {
    pub host: String,
    pub port: u16,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct DetectedPort {
    pub path: String,
    /// usb_printer | serial
    pub kind: String,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Detection {
    pub printers: Vec<DetectedPrinter>,
    pub network: Vec<NetworkPrinter>,
    pub ports: Vec<DetectedPort>,
    /// The local network that was searched (e.g. "192.168.1.0/24"), if any.
    pub subnet: Option<String>,
    pub network_scanned: bool,
}

pub const RAW_PRINT_PORT: u16 = 9100;

/// What a printer probably is, from its name and driver.
pub fn guess_kind(name: &str, driver: &str) -> &'static str {
    let s = format!("{} {}", name, driver).to_lowercase();
    const VIRTUAL: [&str; 7] = ["print to pdf", "xps", "onenote", "fax", "pdf printer", "send to", "cups-pdf"];
    const LABEL: [&str; 10] = ["zebra", "zdesigner", "label", "etiquette", "étiquette", "tsc ", "godex", "gk420", "zd4", "brother ql"];
    const RECEIPT: [&str; 15] = ["receipt", "ticket", "pos-", "pos ", "pos80", "pos58", "tm-", "thermal", "xprinter", "80mm", "58mm",
        "rongta", "bixolon", "generic / text", "esc/pos"];
    if VIRTUAL.iter().any(|k| s.contains(k)) {
        "virtual"
    } else if LABEL.iter().any(|k| s.contains(k)) {
        "label"
    } else if RECEIPT.iter().any(|k| s.contains(k)) || s.starts_with("pos") {
        "receipt"
    } else {
        "office"
    }
}

/// Address of this PC on its local network and the /24 around it. Only private
/// networks are searched (never a public address range).
pub fn local_subnet() -> Option<(Ipv4Addr, String, Vec<Ipv4Addr>)> {
    // "Connecting" a UDP socket sends nothing: it only asks the system which
    // interface it would use, which gives the PC's LAN address.
    let sock = UdpSocket::bind("0.0.0.0:0").ok()?;
    sock.connect("192.0.2.1:9").or_else(|_| sock.connect("8.8.8.8:80")).ok()?;
    let ip = match sock.local_addr().ok()?.ip() {
        IpAddr::V4(v4) => v4,
        IpAddr::V6(_) => return None,
    };
    subnet_hosts(ip).map(|(label, hosts)| (ip, label, hosts))
}

/// The other addresses of a private /24 network (1..=254, without `own`).
pub fn subnet_hosts(own: Ipv4Addr) -> Option<(String, Vec<Ipv4Addr>)> {
    if !own.is_private() || own.is_loopback() {
        return None;
    }
    let [a, b, c, _] = own.octets();
    let hosts = (1..=254u8).map(|d| Ipv4Addr::new(a, b, c, d)).filter(|h| *h != own).collect();
    Some((format!("{}.{}.{}.0/24", a, b, c), hosts))
}

/// Addresses (in the given order) that accept a TCP connection on `port`.
/// Nothing is sent: the connection is opened and closed.
pub fn scan_hosts(hosts: &[IpAddr], port: u16, timeout: Duration, workers: usize) -> Vec<String> {
    let queue = Arc::new(Mutex::new(hosts.iter().cloned().enumerate().collect::<Vec<_>>()));
    let found = Arc::new(Mutex::new(Vec::<(usize, String)>::new()));
    let mut threads = Vec::new();
    for _ in 0..workers.max(1).min(hosts.len().max(1)) {
        let queue = Arc::clone(&queue);
        let found = Arc::clone(&found);
        threads.push(std::thread::spawn(move || loop {
            let next = queue.lock().ok().and_then(|mut q| q.pop());
            let Some((i, host)) = next else { break };
            if TcpStream::connect_timeout(&SocketAddr::new(host, port), timeout).is_ok() {
                if let Ok(mut f) = found.lock() {
                    f.push((i, host.to_string()));
                }
            }
        }));
    }
    for t in threads {
        let _ = t.join();
    }
    let mut out = found.lock().map(|f| f.clone()).unwrap_or_default();
    out.sort();
    out.into_iter().map(|(_, h)| h).collect()
}

/// Printers on the local network (raw printing port 9100).
pub fn scan_network() -> (Option<String>, Vec<NetworkPrinter>) {
    let Some((_, label, hosts)) = local_subnet() else { return (None, Vec::new()) };
    let hosts: Vec<IpAddr> = hosts.into_iter().map(IpAddr::V4).collect();
    let found = scan_hosts(&hosts, RAW_PRINT_PORT, Duration::from_millis(450), 64);
    (Some(label), found.into_iter().map(|host| NetworkPrinter { host, port: RAW_PRINT_PORT }).collect())
}

/// Serial and USB printer ports of this PC.
pub fn list_ports() -> Vec<DetectedPort> {
    let mut out = Vec::new();
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        // Every COM port Windows knows (USB-serial adapters included).
        if let Ok(o) = std::process::Command::new("reg")
            .args(["query", r"HKLM\HARDWARE\DEVICEMAP\SERIALCOMM"])
            .creation_flags(CREATE_NO_WINDOW)
            .output()
        {
            for com in parse_serialcomm(&String::from_utf8_lossy(&o.stdout)) {
                out.push(DetectedPort { path: com, kind: "serial".into() });
            }
        }
    }
    #[cfg(not(windows))]
    {
        let rules: [(&str, &str, &str); 5] = [
            ("/dev/usb", "lp", "usb_printer"),
            ("/dev", "usb/lp", "usb_printer"),
            ("/dev", "ttyUSB", "serial"),
            ("/dev", "ttyACM", "serial"),
            ("/dev", "cu.usb", "serial"),
        ];
        for (dir, prefix, kind) in rules {
            if let Ok(entries) = std::fs::read_dir(dir) {
                for e in entries.flatten() {
                    let name = e.file_name().to_string_lossy().to_string();
                    if name.starts_with(prefix) {
                        let path = format!("{}/{}", dir, name);
                        if !out.iter().any(|p: &DetectedPort| p.path == path) {
                            out.push(DetectedPort { path, kind: kind.into() });
                        }
                    }
                }
            }
        }
    }
    out.sort_by(|a, b| a.path.cmp(&b.path));
    out
}

/// COM port names from `reg query HKLM\HARDWARE\DEVICEMAP\SERIALCOMM`.
pub fn parse_serialcomm(text: &str) -> Vec<String> {
    let mut v: Vec<String> = text
        .lines()
        .filter(|l| l.contains("REG_SZ"))
        .filter_map(|l| l.split_whitespace().last())
        .filter(|w| w.to_ascii_uppercase().starts_with("COM"))
        .map(|w| w.to_string())
        .collect();
    v.sort_by_key(|c| c[3..].parse::<u32>().unwrap_or(u32::MAX));
    v.dedup();
    v
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn printer_kinds_are_guessed_from_name_and_driver() {
        assert_eq!(guess_kind("Microsoft Print to PDF", ""), "virtual");
        assert_eq!(guess_kind("ZDesigner GK420t", "ZDesigner GK420t"), "label");
        assert_eq!(guess_kind("POS-80C", "POS-80C"), "receipt");
        assert_eq!(guess_kind("Caisse", "Generic / Text Only"), "receipt");
        assert_eq!(guess_kind("EPSON TM-T20II Receipt", ""), "receipt");
        assert_eq!(guess_kind("HP LaserJet Pro M404", "HP Universal"), "office");
    }

    #[test]
    fn only_private_networks_are_searched() {
        let (label, hosts) = subnet_hosts(Ipv4Addr::new(192, 168, 1, 23)).unwrap();
        assert_eq!(label, "192.168.1.0/24");
        assert_eq!(hosts.len(), 253);
        assert!(!hosts.contains(&Ipv4Addr::new(192, 168, 1, 23)));
        assert!(subnet_hosts(Ipv4Addr::new(41, 107, 3, 9)).is_none());
        assert!(subnet_hosts(Ipv4Addr::new(127, 0, 0, 1)).is_none());
    }

    #[test]
    fn scan_finds_the_address_that_listens_and_sends_nothing() {
        use std::io::Read;
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let server = std::thread::spawn(move || {
            let (mut s, _) = listener.accept().unwrap();
            let mut got = Vec::new();
            let _ = s.read_to_end(&mut got);
            got
        });
        // 127.0.0.1 listens; 127.0.0.2 (same machine, other address) does not on Linux.
        let hosts: Vec<IpAddr> = vec!["127.0.0.2".parse().unwrap(), "127.0.0.1".parse().unwrap()];
        let found = scan_hosts(&hosts, port, Duration::from_millis(300), 4);
        assert!(found.contains(&"127.0.0.1".to_string()), "{:?}", found);
        assert!(server.join().unwrap().is_empty(), "the scan must not send anything to a printer");
    }

    #[test]
    fn com_ports_are_read_from_the_registry_listing() {
        let text = "\r\nHKEY_LOCAL_MACHINE\\HARDWARE\\DEVICEMAP\\SERIALCOMM\r\n    \\Device\\Serial0    REG_SZ    COM1\r\n    \\Device\\VCP0    REG_SZ    COM12\r\n    \\Device\\USBSER000    REG_SZ    COM3\r\n";
        assert_eq!(parse_serialcomm(text), vec!["COM1", "COM3", "COM12"]);
    }
}
