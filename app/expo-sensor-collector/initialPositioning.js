function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function circularDistance(a, b) {
  return Math.abs(((a - b + 540) % 360) - 180);
}

function classifyCorridorDirection(heading) {
  if (!Number.isFinite(heading)) return { sign: -1, label: "방향 미확정", confidence: "low" };
  const rightDistance = circularDistance(heading, 350);
  const leftDistance = circularDistance(heading, 175);
  const coreDistance = circularDistance(heading, 270);
  if (coreDistance <= 35) return { sign: rightDistance <= leftDistance ? -1 : 1, label: "코어→메인복도 후보", confidence: "medium" };
  if (rightDistance <= leftDistance) return { sign: -1, label: "오른쪽 복도 방향", confidence: rightDistance <= 40 ? "high" : "low" };
  return { sign: 1, label: "왼쪽 복도 방향", confidence: leftDistance <= 45 ? "high" : "low" };
}

function rankStationaryCandidates({ platform, magneticValues, pressureValues, references, transferModels = [] }) {
  const magneticMedian = median(magneticValues);
  const pressureMedian = median(pressureValues);
  if (magneticMedian === null) return { candidates: [], magneticMedian, pressureMedian, confidence: "none" };
  const direct = references.filter((reference) => reference.platform === platform);
  const directKeys = new Set(direct.map((reference) => `${reference.floor}:${reference.node_id}`));
  const transfer = transferModels.find((model) => model.target_platform === platform);
  const transferred = transfer ? references
    .filter((reference) => reference.platform === transfer.source_platform && !directKeys.has(`${reference.floor}:${reference.node_id}`))
    .map((reference) => ({
      ...reference,
      platform,
      transferred_from: transfer.source_platform,
      transfer_penalty: 0.35,
      magnetic_median_ut: transfer.slope * reference.magnetic_median_ut + transfer.intercept,
      magnetic_between_observation_std_ut: Math.abs(transfer.slope) * (reference.magnetic_between_observation_std_ut || 0) + transfer.rmse_ut,
      magnetic_within_window_std_ut: Math.abs(transfer.slope) * (reference.magnetic_within_window_std_ut || 0)
    })) : [];
  const candidates = [...direct, ...transferred]
    .map((reference) => {
      const spread = Math.max(
        2.0,
        (reference.magnetic_between_observation_std_ut || 0) + (reference.magnetic_within_window_std_ut || 0)
      );
      return {
        ...reference,
        score: Math.abs(magneticMedian - reference.magnetic_median_ut) / spread + (reference.transfer_penalty || 0),
        magneticDifferenceUt: Math.abs(magneticMedian - reference.magnetic_median_ut),
        pressureDifferenceHpa: pressureMedian === null || reference.pressure_median_hpa == null
          ? null
          : Math.abs(pressureMedian - reference.pressure_median_hpa)
      };
    })
    .sort((a, b) => a.score - b.score);
  const first = candidates[0];
  const second = candidates[1];
  const margin = first && second ? second.score - first.score : 0;
  let confidence = "low";
  if (first?.observation_count >= 2 && first.score <= 0.65 && margin >= 0.45) confidence = "medium";
  return { candidates: candidates.slice(0, 3), magneticMedian, pressureMedian, confidence, margin };
}

module.exports = {
  circularDistance,
  classifyCorridorDirection,
  median,
  rankStationaryCandidates
};
