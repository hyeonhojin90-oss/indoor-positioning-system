import { requireOptionalNativeModule } from "expo-modules-core";

// Expo Go does not contain this local native module. Optional loading keeps
// the existing Expo Go collector usable while making the capability explicit.
const BleSurvey = requireOptionalNativeModule("BleSurvey");

export function isBleSurveyAvailable() {
  return BleSurvey !== null;
}

export function getBleSurveyState() {
  return BleSurvey?.getState?.() ?? { state: "native_module_unavailable" };
}

export async function startBleSurveyScan() {
  if (!BleSurvey) {
    throw new Error("BLE 환경조사는 설치형 iPhone 개발 앱에서만 사용할 수 있습니다.");
  }
  return BleSurvey.startScan(true);
}

export function stopBleSurveyScan() {
  BleSurvey?.stopScan?.();
}

export function addBleSurveyListener(eventName, listener) {
  if (!BleSurvey) return { remove() {} };
  return BleSurvey.addListener(eventName, listener);
}
