// script.js

const inputVideo = document.getElementById("input-video");
const outputCanvas = document.getElementById("output-canvas");
const ctx = outputCanvas.getContext("2d");

let allLandmarks = []; // ⬅️ Store all pose landmarks

// Load and play uploaded video
document.getElementById("upload-video").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (file) {
    inputVideo.src = URL.createObjectURL(file);
    inputVideo.load();
    inputVideo.play();
    allLandmarks = []; // reset when a new video is uploaded
  }
});

// Initialize MediaPipe Pose
const pose = new Pose.Pose({
  locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5/${file}`,
});

pose.setOptions({
  modelComplexity: 1,
  minDetectionConfidence: 0.5,
  minTrackingConfidence: 0.5,
});

pose.onResults((results) => {
  ctx.save();
  ctx.clearRect(0, 0, outputCanvas.width, outputCanvas.height);
  ctx.drawImage(results.image, 0, 0, outputCanvas.width, outputCanvas.height);

  if (results.poseLandmarks) {
    allLandmarks.push(results.poseLandmarks); // ✅ store this frame's pose
    drawConnectors(ctx, results.poseLandmarks, Pose.POSE_CONNECTIONS, {
      color: "#00FF00",
      lineWidth: 3,
    });
    drawLandmarks(ctx, results.poseLandmarks, {
      color: "#FF0000",
      lineWidth: 2,
    });
  }

  ctx.restore();
});

// Feed frames to MediaPipe
inputVideo.addEventListener("play", () => {
  const processFrame = async () => {
    if (!inputVideo.paused && !inputVideo.ended) {
      await pose.send({ image: inputVideo });
      requestAnimationFrame(processFrame);
    }
  };
  requestAnimationFrame(processFrame);
});

// When video ends, run form analysis
inputVideo.addEventListener("ended", () => {
  console.log("Video ended. Running form analysis...");
  analyzeForm(allLandmarks);
});

// Analyze form logic
function analyzeForm(allLandmarks) {
  let badSquatFrames = 0;
  let badBenchFrames = 0;
  let badPullupFrames = 0;

  allLandmarks.forEach((landmarks) => {
    // SQUAT (side view)
    const hip = landmarks[24];
    const knee = landmarks[26];
    const ankle = landmarks[28];
    const squatAngle = getAngle(hip, knee, ankle);
    if (squatAngle > 130) {
      badSquatFrames++;
    }

    // BENCH PRESS (side view)
    const shoulder = landmarks[12];
    const elbow = landmarks[14];
    const wrist = landmarks[16];
    const elbowAngle = getAngle(shoulder, elbow, wrist);
    if (elbowAngle < 70 || elbowAngle > 120) {
      badBenchFrames++;
    }

    // PULL-UP (front view)
    const nose = landmarks[0];
    const wristL = landmarks[15];
    const wristR = landmarks[16];
    const barY = Math.min(wristL.y, wristR.y);
    if (nose.y > barY) {
      badPullupFrames++;
    }
  });

  const percent = (count) =>
    ((count / allLandmarks.length) * 100).toFixed(1);

  let messages = [];

  if (percent(badSquatFrames) > 30)
    messages.push("⚠️ Squats too shallow in many frames.");
  else messages.push("✅ Squat depth looks good!");

  if (percent(badBenchFrames) > 30)
    messages.push("⚠️ Elbows flaring during bench press.");
  else messages.push("✅ Bench press elbow form looks controlled.");

  if (percent(badPullupFrames) > 30)
    messages.push("⚠️ Chin not clearing the bar during pull-ups.");
  else messages.push("✅ Pull-up height is good!");

  alert(messages.join("\n"));
}

// Helper to compute angle at joint B
function getAngle(a, b, c) {
  const ab = { x: b.x - a.x, y: b.y - a.y };
  const cb = { x: b.x - c.x, y: b.y - c.y };
  const dot = ab.x * cb.x + ab.y * cb.y;
  const magAB = Math.hypot(ab.x, ab.y);
  const magCB = Math.hypot(cb.x, cb.y);
  const angleRad = Math.acos(dot / (magAB * magCB));
  return (angleRad * 180) / Math.PI;
}