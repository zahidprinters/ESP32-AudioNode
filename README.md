# AudioNode — WiFi speaker box

A **networked speaker box**: an ESP32-S3 board that joins your WiFi, receives PCM audio over RTP/UDP from a server on the same network, and plays it out through a MAX98357A class-D amp.

**One-time setup**: power the board on → it runs a setup WiFi AP → connect your phone/laptop to it → open the web page → enter your WiFi + server address → the board switches to your network and listens for RTP. From then on it plays whenever the server is sending.

**Multiple nodes**: run the same server stream to several boards (unicast to each board IP:port). One transmitter, many speakers.
