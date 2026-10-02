# External research data

Large third-party source files are not committed. Their provenance and every
derived experiment are recorded in the analysis report instead.

## RIDI

- Name: Robust IMU Double Integration (RIDI)
- Original project: <https://yanhangpublic.github.io/ridi/>
- Archive URL used: <https://www.dropbox.com/s/9zzaj3h3u4bta23/ridi_data_publish_v2.zip?dl=1>
- Archive SHA-256: `c454921f16a925dcd3a6545480531d770208b590b677e2e9a92877ed2d661c25`
- Download date: 2026-09-14
- Use: analysis-only public stride-prior experiment. It is not bundled into
  the app and does not update the deployed motion model.

The source project and its data-use terms govern the archive. See
`../analysis/detailed-20260914/public-ridi-stride-v1.json` for the exact
experiment split, derived model, and local holdout results.

## ADVIO

- Name: An Authentic Dataset for Visual-Inertial Odometry (ADVIO)
- Original project: <https://github.com/AaltoVision/ADVIO>
- Archive URLs used: `https://zenodo.org/records/1476931/files/advio-{13,16,17,19}.zip`
- Download date: 2026-09-14
- Use: analysis-only iPhone CoreMotion stride-transfer experiment. The four
  archives are Office 01/04/05/07, each with stairs; they are not bundled into
  the app and do not update the deployed motion model.

The downloaded archive hashes, exact detector replay, source route holdouts,
and local 4F transfer result are in
`../analysis/detailed-20260914/advio-iphone-stride-v1.json`.

## Walking Recognition Dataset

- Name: Walking Recognition Dataset
- Original project: <https://citius.usc.es/investigacion/datasets/walking-recognition-dataset>
- Archive URL used: <https://gitlab.citius.gal/fernando.estevez/walking-recognition-dataset/-/archive/master/archive.zip>
- Archive SHA-256: `517ce737d6b648e3eb71805ca0031bf0b07f52dc25d5645bec1bba34f854ebf9`
- Download date: 2026-09-14
- Use: analysis-only detector-confidence experiment. Its foot-sensor step
  timestamps are used to test the existing Expo peak detector, not to update
  the app or Fusion runtime.

The archive is not committed. `experiment_wrd_step_confidence.py` and
`../analysis/detailed-20260914/wrd-step-confidence-v1.json` preserve the exact
detector, user-held-out evaluation, feature ablation, and local transfer test.
