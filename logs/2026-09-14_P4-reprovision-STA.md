Your environment is not configured to handle Unicode characters.

Recommended fix (persistent):
 - Enable "Beta: Use Unicode UTF-8 for worldwide language support" in Windows language/region settings.

If you still see issues or this warning persists, you can also try one of these workarounds:
 - Run "chcp 65001" in the current console before running idf.py.
 - Set PYTHONUTF8=1 before running idf.py (or set it globally).

Note: "chcp 65001" must be run in each new console session unless your console/profile is configured to apply it automatically.
--- WARNING: GDB cannot open serial ports accessed as COMx

--- NOTE: Using \\.\COM5 instead...

--- esp-idf-monitor 1.10.0 on \\.\COM5 115200

--- Standard input is not a TTY, running in non-interactive mode. Reading commands from stdin: reset, flash, flash-all, app-flash, output, log, timestamps, bootloader, send <text>, sleep <seconds>, expect [--timeout <seconds>] <regex>, exit | Quit: 'exit' command, EOF or Ctrl+C

--- No commands on standard input, watching serial output only...

Executing action: monitor
Running idf_monitor in directory D:\esp-idf\audio_node
Executing "C:\Espressif\tools\python\v6.1\venv\Scripts\python.exe d:\esp32\v6.1\esp-idf\tools/idf_monitor.py -p COM5 -b 115200 --toolchain-prefix xtensa-esp32s3-elf- --target esp32s3 --revision 0 D:\esp-idf\audio_node\build\audio_node.elf D:\esp-idf\audio_node\build\bootloader\bootloader.elf --no-reset --force-color -m 'C:\Espressif\tools\python\v6.1\venv\Scripts\python.exe' 'd:\esp32\v6.1\esp-idf\tools\idf.py' '-p' 'COM5'"...
I (373166) wifi:new:<1,0>, old:<1,1>, ap:<1,1>, sta:<255,255>, prof:1, snd_ch_cfg:0x0

I (373166) wifi:station: a4:c3:f0:3c:f1:7c join, AID=1, bgn, 20

I (373506) esp_netif_lwip: DHCP server assigned IP to a client, IP is: 192.168.4.2

I (381746) wifi:<ba-add>idx:2 (ifx:1, a4:c3:f0:3c:f1:7c), tid:0, ssn:51, winSize:64

I (431056) wifi:station: a4:c3:f0:3c:f1:7c leave, AID = 1, reason = 1, bss_flags is 33721443, bss:0x3fca961c

I (431056) wifi:<ba-del>idx:2, tid:0

I (431056) wifi:new:<1,1>, old:<1,0>, ap:<1,1>, sta:<255,255>, prof:1, snd_ch_cfg:0x0

I (523046) wifi:new:<1,0>, old:<1,1>, ap:<1,1>, sta:<255,255>, prof:1, snd_ch_cfg:0x0

I (523046) wifi:station: a4:c3:f0:3c:f1:7c join, AID=1, bgn, 20

I (523106) esp_netif_lwip: DHCP server assigned IP to a client, IP is: 192.168.4.2

I (525596) wifi:<ba-add>idx:2 (ifx:1, a4:c3:f0:3c:f1:7c), tid:0, ssn:21, winSize:64

W (548996) httpd_uri: httpd_uri: URI '/favicon.ico' not found

W (548996) httpd_txrx: httpd_resp_send_err: 404 Not Found - Nothing matches the given URI

cfg: saved via portal (SSID=<ssid> server=<pc-ip>:1234)

I (586406) wifi:station: a4:c3:f0:3c:f1:7c leave, AID = 1, reason = 2, bss_flags is 33721443, bss:0x3fca961c

I (586406) wifi:<ba-del>idx:2, tid:0

I (586406) wifi:new:<1,1>, old:<1,0>, ap:<1,1>, sta:<255,255>, prof:1, snd_ch_cfg:0x0

I (586456) wifi:flush txq

I (586456) wifi:stop sw txq

I (586456) wifi:lmac stop hw txq

ESP-ROM:esp32s3-20210327

Build:Mar 27 2021

rst:0xc (RTC_SW_CPU_RST),boot:0x8 (SPI_FAST_FLASH_BOOT)

Saved PC:0x403802cd

--- 0x403802cd: esp_restart_noos at D:/esp32/v6.1/esp-idf/components/esp_system/port/soc/esp32s3/system_internal.c:171

SPIWP:0xee

mode:DIO, clock div:1

load:0x3fce2820,len:0x14f0

load:0x403c8700,len:0xde4

--- 0x403c8700: _stext at ??:?

load:0x403cb700,len:0x2f58

entry 0x403c8904

--- 0x403c8904: call_start_cpu0 at D:/esp32/v6.1/esp-idf/components/bootloader/subproject/main/bootloader_start.c:27

I (24) boot: ESP-IDF v6.1 2nd stage bootloader

I (24) boot: compile time Sep 13 2026 18:50:26

I (24) boot: Multicore bootloader

I (24) boot: chip revision: v0.2

I (27) boot: efuse block revision: v1.3

I (30) boot.esp32s3: Boot SPI Speed : 80MHz

I (34) boot.esp32s3: SPI Mode       : DIO

I (38) boot.esp32s3: SPI Flash Size : 8MB

I (42) boot: Enabling RNG early entropy source...

I (46) boot: Partition Table:

I (49) boot: ## Label            Usage          Type ST Offset   Length

I (55) boot:  0 nvs              WiFi data        01 02 00009000 00006000

I (62) boot:  1 phy_init         RF data          01 01 0000f000 00001000

I (68) boot:  2 factory          factory app      00 00 00010000 00100000

I (75) boot: End of partition table

I (78) esp_image: segment 0: paddr=00010020 vaddr=3c0a0020 size=22004h (139268) map

I (111) esp_image: segment 1: paddr=0003202c vaddr=3fc9ad00 size=05850h ( 22608) load

I (116) esp_image: segment 2: paddr=00037884 vaddr=40374000 size=08794h ( 34708) load

I (124) esp_image: segment 3: paddr=00040020 vaddr=42000020 size=9db14h (645908) map

I (243) esp_image: segment 4: paddr=000ddb3c vaddr=4037c794 size=0e490h ( 58512) load

I (257) esp_image: segment 5: paddr=000ebfd4 vaddr=50000000 size=00024h (    36) load

I (267) boot: Loaded app from partition at offset 0x10000

I (267) boot: Disabling RNG early entropy source...

I (277) octal_psram: vendor id    : 0x0d (AP)

I (277) octal_psram: dev id       : 0x02 (generation 3)

I (277) octal_psram: density      : 0x03 (64 Mbit)

I (279) octal_psram: good-die     : 0x01 (Pass)

I (284) octal_psram: Latency      : 0x01 (Fixed)

I (288) octal_psram: VCC          : 0x01 (3V)

I (292) octal_psram: SRF          : 0x01 (Fast Refresh)

I (297) octal_psram: BurstType    : 0x01 (Hybrid Wrap)

I (302) octal_psram: BurstLen     : 0x01 (32 Byte)

I (306) octal_psram: Readlatency  : 0x02 (10 cycles@Fixed)

I (312) octal_psram: DriveStrength: 0x00 (1/1)

I (316) MSPI Timing: Enter psram timing tuning

I (321) esp_psram: Found 8MB PSRAM device

I (324) esp_psram: Speed: 80MHz

I (327) cpu_start: Multicore app

I (762) esp_psram: SPI SRAM memory test OK

I (771) cpu_start: GPIO 44 and 43 are used as console UART I/O pins

I (771) cpu_start: Pro cpu start user code

I (771) cpu_start: cpu freq: 160000000 Hz

I (773) app_init: Application information:

I (777) app_init: Project name:     audio_node

I (781) app_init: App version:      f97e36d-dirty

I (785) app_init: Compile time:     Sep 14 2026 22:13:31

I (790) app_init: ELF file SHA256:  878c0f43d...

I (795) app_init: ESP-IDF:          v6.1

I (798) efuse_init: Min chip rev:     v0.0

I (802) efuse_init: Max chip rev:     v0.99 

I (806) efuse_init: Chip rev:         v0.2

I (810) heap_init: Initializing. RAM available for dynamic allocation:

I (816) heap_init: At 3FCA6920 len 00042DF0 (267 KiB): RAM

I (821) heap_init: At 3FCE9710 len 00005724 (21 KiB): RAM

I (826) heap_init: At 3FCF0000 len 00008000 (32 KiB): DRAM

I (832) heap_init: At 600FE000 len 00001FE8 (7 KiB): RTCRAM

I (837) esp_psram: Adding pool of 8192K of PSRAM memory to heap allocator

I (844) spi_flash: detected chip: generic

I (847) spi_flash: flash io: dio

W (850) spi_flash: Detected size(16384k) larger than the size in the binary image header(8192k). Using the size in the binary image header.

I (863) sleep_gpio: Configure to isolate all GPIO pins in sleep state

I (869) sleep_gpio: Enable automatic switching of GPIO sleep configuration

I (876) main_task: Started on CPU0

I (876) esp_psram: Reserving pool of 32K of internal memory for DMA/internal allocations

I (886) main_task: Calling app_main()

audio_node: WiFi streamer start

I2S: 48000 Hz, 16-bit mono, BCLK=4 LRC=5 DIN=6 SD=15 RGB=48

I (926) pp: pp rom version: e7ae62f

I (926) net80211: net80211 rom version: e7ae62f

I (936) wifi:wifi driver task: 3fcb7c60, prio:23, stack:6656, core=0

I (936) wifi:wifi firmware version: e12a754

I (936) wifi:wifi certification version: v7.0

I (936) wifi:config NVS flash: enabled

I (946) wifi:config nano formatting: disabled

I (946) wifi:Init data frame dynamic rx buffer num: 32

I (956) wifi:Init static rx mgmt buffer num: 5

I (956) wifi:Init management short buffer num: 32

I (956) wifi:Init dynamic tx buffer num: 32

I (966) wifi:Init static tx FG buffer num: 2

I (966) wifi:Init static rx buffer size: 1600

I (976) wifi:Init static rx buffer num: 10

I (976) wifi:Init dynamic rx buffer num: 32

I (976) wifi_init: rx ba win: 6

I (986) wifi_init: accept mbox: 6

I (986) wifi_init: tcpip mbox: 32

I (986) wifi_init: udp mbox: 6

I (996) wifi_init: tcp mbox: 6

I (996) wifi_init: tcp tx win: 5760

I (996) wifi_init: tcp rx win: 5760

I (996) wifi_init: tcp mss: 1440

I (1006) wifi_init: WiFi IRAM OP enabled

I (1006) wifi_init: WiFi RX IRAM OP enabled

cfg: server whitelist <pc-ip>

W (1026) wifi:Password length matches WPA2 standards, authmode threshold changes from OPEN to WPA2

I (1056) phy_init: phy_version 712,87e8c20e,Apr 13 2026,18:51:10

I (1096) phy_init: Saving new calibration data due to checksum failure or outdated calibration data, mode(0)

I (1116) wifi:mode : sta (30:30:f9:33:91:d8)

I (1116) wifi:enable tsf

I (1116) wifi:Set ps type: 0, coexist: 0



STA: joining <ssid>

wifi: STA mode, power-save OFF, listening on :1234

udp: listening on 0.0.0.0:1234, waiting for RTP L16 (PT=96)...

I (1126) main_task: Returned from app_main()

I (2286) wifi:new:<10,0>, old:<1,0>, ap:<255,255>, sta:<10,0>, prof:1, snd_ch_cfg:0x0

I (2286) wifi:state: init -> auth (0xb0)

I (2296) wifi:state: auth -> assoc (0x0)

I (2296) wifi:state: assoc -> run (0x10)

I (2406) wifi:connected with <ssid>, aid = 2, channel 10, BW20, bssid = e8:68:19:3c:f0:88

I (2416) wifi:security: WPA2-PSK, phy: bgn, rssi: -33, cipher(pairwise:0x3, group:0x1), pmf:0

I (2426) wifi:pm start, type: 0



I (2426) wifi:dp: 1, bi: 102400, li: 3, scale listen interval from 307200 us to 307200 us

I (2426) wifi:set rx beacon pti, rx_bcn_pti: 0, bcn_timeout: 25000, mt_pti: 0, mt_time: 10000

I (2476) wifi:AP's beacon interval = 102400 us, DTIM period = 1

I (2866) wifi:<ba-add>idx:0 (ifx:0, e8:68:19:3c:f0:88), tid:0, ssn:2, winSize:64

I (5656) esp_netif_handlers: sta ip: <board-ip>, mask: 255.255.255.0, gw: 192.168.100.1

GOT IP: <board-ip>

rssi=-40

rssi=-35

rssi=-40

rssi=-39

rssi=-38

rssi=-39

rssi=-32

rssi=-31

rssi=-34

rssi=-39

rssi=-39

rssi=-38

rssi=-34

rssi=-40

rssi=-34

rssi=-40

rssi=-39

rssi=-35

rssi=-34

udp: pkts=1 dropped=0 ring=1920 pcm=1920 bytes (t=193856 ms)

udp: pkts=252 dropped=0 ring=6528 pcm=483840 bytes (t=198868 ms)

rssi=-40

udp: pkts=503 dropped=0 ring=7168 pcm=965760 bytes (t=203886 ms)

rssi=-39

rssi=-40

rssi=-40

rssi=-40

rssi=-37

rssi=-39

rssi=-40

rssi=-31

