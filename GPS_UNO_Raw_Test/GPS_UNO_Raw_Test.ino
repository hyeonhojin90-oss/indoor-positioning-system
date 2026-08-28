#include <SoftwareSerial.h>

// GPS TX -> Arduino D4
// GPS RX -> Arduino D3, or leave disconnected for this read-only test
SoftwareSerial gpsSerial(4, 3); // RX, TX

const unsigned long PC_BAUD = 9600;
const unsigned long GPS_BAUD = 9600;
unsigned long lastDataTime = 0;

void setup() {
  Serial.begin(PC_BAUD);
  gpsSerial.begin(GPS_BAUD);

  Serial.println();
  Serial.println("=== NEO-7M GPS raw data test ===");
  Serial.println("Wiring: GPS TX -> UNO D4, GPS GND -> UNO GND");
  Serial.println("Waiting for NMEA data...");
}

void loop() {
  bool received = false;

  while (gpsSerial.available() > 0) {
    char c = gpsSerial.read();
    Serial.write(c);
    received = true;
  }

  if (received) {
    lastDataTime = millis();
  }

  if (millis() - lastDataTime > 5000) {
    Serial.println();
    Serial.println("[No GPS data for 5 seconds]");
    Serial.println("Check GPS TX -> UNO D4, common GND, power, and GPS baud rate.");
    lastDataTime = millis();
  }
}
