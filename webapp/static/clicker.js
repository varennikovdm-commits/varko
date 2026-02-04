let power = 0;
let level = 1;

const powerEl = document.getElementById("power");
const levelEl = document.getElementById("level");
const sunEl = document.getElementById("sun");
const glowEl = document.getElementById("glow");
const upgradeText = document.getElementById("upgrade-text");

const levels = [
  { threshold: 0, message: "Солнышко только проснулось. Продолжайте клики, чтобы усилить сияние." },
  { threshold: 10, message: "Сияние стало теплее. Фон начинает согреваться." },
  { threshold: 40, message: "Солнце уверенно светит! Лучи становятся ярче." },
  { threshold: 100, message: "Небо залито светом. Почти летний день." },
];

function updateLevel() {
  const newLevel = levels.reduce((acc, item, index) => {
    if (power >= item.threshold) {
      return index + 1;
    }
    return acc;
  }, 1);

  if (newLevel !== level) {
    level = newLevel;
    levelEl.textContent = String(level);
    document.body.className = `level-${level}`;
    upgradeText.textContent = levels[level - 1].message;
    gsap.to(glowEl, {
      scale: 1 + level * 0.1,
      duration: 0.6,
      ease: "power2.out",
    });
  }
}

function spawnFloatingText() {
  const floating = document.createElement("div");
  floating.className = "floating";
  floating.textContent = "+1";
  floating.style.left = `${Math.random() * 80 + 10}%`;
  floating.style.top = "50%";
  sunEl.parentElement.appendChild(floating);

  gsap.fromTo(
    floating,
    { y: 0, opacity: 1 },
    {
      y: -60,
      opacity: 0,
      duration: 1,
      ease: "power1.out",
      onComplete: () => floating.remove(),
    }
  );
}

sunEl.addEventListener("click", () => {
  power += 1;
  powerEl.textContent = String(power);
  updateLevel();
  spawnFloatingText();

  gsap.fromTo(
    sunEl,
    { scale: 1 },
    { scale: 1.1, duration: 0.15, yoyo: true, repeat: 1, ease: "power1.inOut" }
  );
});

updateLevel();
