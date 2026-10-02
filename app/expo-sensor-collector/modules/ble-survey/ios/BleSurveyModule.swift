import CoreBluetooth
import ExpoModulesCore

public final class BleSurveyModule: Module, CBCentralManagerDelegate {
  private var centralManager: CBCentralManager?
  private var isScanning = false

  public func definition() -> ModuleDefinition {
    Name("BleSurvey")

    Events("onBluetoothState", "onAdvertisement")

    OnCreate {
      self.ensureCentralManager()
    }

    Function("getState") {
      return ["state": self.bluetoothStateName(self.centralManager?.state ?? .unknown)]
    }

    AsyncFunction("startScan") { (allowDuplicates: Bool) throws -> [String: Any] in
      self.ensureCentralManager()
      guard let manager = self.centralManager else {
        throw NSError(domain: "BleSurvey", code: 1, userInfo: [NSLocalizedDescriptionKey: "Bluetooth manager를 만들지 못했습니다."])
      }
      guard manager.state == .poweredOn else {
        throw NSError(domain: "BleSurvey", code: 2, userInfo: [NSLocalizedDescriptionKey: "Bluetooth가 꺼져 있거나 아직 준비되지 않았습니다."])
      }
      self.isScanning = true
      manager.scanForPeripherals(
        withServices: nil,
        options: [CBCentralManagerScanOptionAllowDuplicatesKey: allowDuplicates]
      )
      return ["state": self.bluetoothStateName(manager.state), "scanning": true]
    }

    Function("stopScan") {
      self.centralManager?.stopScan()
      self.isScanning = false
    }

    OnDestroy {
      self.centralManager?.stopScan()
      self.centralManager?.delegate = nil
      self.isScanning = false
    }
  }

  private func ensureCentralManager() {
    if centralManager == nil {
      centralManager = CBCentralManager(delegate: self, queue: DispatchQueue.main)
    }
  }

  public func centralManagerDidUpdateState(_ central: CBCentralManager) {
    sendEvent("onBluetoothState", [
      "state": bluetoothStateName(central.state),
      "scanning": isScanning
    ])
  }

  public func centralManager(
    _ central: CBCentralManager,
    didDiscover peripheral: CBPeripheral,
    advertisementData: [String: Any],
    rssi RSSI: NSNumber
  ) {
    let serviceUUIDs = (advertisementData[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID] ?? [])
      .map { $0.uuidString.lowercased() }
    let overflowServiceUUIDs = (advertisementData[CBAdvertisementDataOverflowServiceUUIDsKey] as? [CBUUID] ?? [])
      .map { $0.uuidString.lowercased() }
    let txPower = (advertisementData[CBAdvertisementDataTxPowerLevelKey] as? NSNumber)?.intValue
    let connectable = (advertisementData[CBAdvertisementDataIsConnectable] as? NSNumber)?.boolValue

    // The raw identifier and advertised name are sent only to the active app
    // for display. The JavaScript logger stores a pseudonymous identifier and
    // omits the advertised name from JSONL files.
    sendEvent("onAdvertisement", [
      "peripheralId": peripheral.identifier.uuidString,
      "name": peripheral.name ?? advertisementData[CBAdvertisementDataLocalNameKey] as? String ?? "",
      "rssi": RSSI.intValue,
      "txPower": txPower ?? NSNull(),
      "serviceUUIDs": serviceUUIDs,
      "overflowServiceUUIDs": overflowServiceUUIDs,
      "manufacturerDataPresent": advertisementData[CBAdvertisementDataManufacturerDataKey] != nil,
      "connectable": connectable ?? NSNull()
    ])
  }

  private func bluetoothStateName(_ state: CBManagerState) -> String {
    switch state {
    case .poweredOn: return "powered_on"
    case .poweredOff: return "powered_off"
    case .unauthorized: return "unauthorized"
    case .unsupported: return "unsupported"
    case .resetting: return "resetting"
    case .unknown: fallthrough
    @unknown default: return "unknown"
    }
  }
}
