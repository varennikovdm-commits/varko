const energyEl = document.getElementById("energy");
const levelEl = document.getElementById("level");
const autoEl = document.getElementById("auto");
const progressLabel = document.getElementById("level-label");
const progressValue = document.getElementById("progress-value");
const progressFill = document.getElementById("progress-fill");
const sun = document.getElementById("sun");
const sunWrapper = document.getElementById("sun-wrapper");
const floating = document.getElementById("floating");
const shop = document.getElementById("shop");
const toggleShop = document.getElementById("toggle-shop");

const upgradeButtons = document.querySelectorAll("[data-upgrade]");

const levels = [0, 20, 60, 140, 260, 500];

const defaultState = {
  energy: 0,
  clickPower: 1,
  autoPower: 0,
  farms: 0,
  costs: {
    click: 10,
    auto: 25,
    farm: 100,
  },
};

const state = loadState();

function loadState() {
  const saved = localStorage.getItem("solarFarmState");
  if (!saved) {
    return { ...defaultState };
  }
  try {
    const parsed = JSON.parse(saved);
    return {
      ...defaultState,
      ...parsed,
      costs: { ...defaultState.costs, ...parsed.costs },
    };
  } catch (error) {
    return { ...defaultState };
  }
}

function saveState() {
  localStorage.setItem("solarFarmState", JSON.stringify(state));
}

function updateUI() {
  energyEl.textContent = Math.floor(state.energy);
  levelEl.textContent = getLevel();
  autoEl.textContent = `${state.autoPower}/сек`;
  updateProgress();
  updateCosts();
  updateSunTheme();
}

function getLevel() {
  let level = 1;
  for (let i = 1; i < levels.length; i += 1) {
    if (state.energy >= levels[i]) {
      level = i + 1;
    }
  }
  return level;
}

function updateProgress() {
  const level = getLevel();
  const current = levels[level - 1] ?? 0;
  const next = levels[level] ?? (levels[levels.length - 1] + 200);
  const progress = Math.min(((state.energy - current) / (next - current)) * 100, 100);
  progressFill.style.width = `${progress}%`;
  progressValue.textContent = `${Math.floor(progress)}%`;
  progressLabel.textContent = `До уровня ${level + 1}`;
}

function updateCosts() {
  document.getElementById("cost-click").textContent = state.costs.click;
  document.getElementById("cost-auto").textContent = state.costs.auto;
  document.getElementById("cost-farm").textContent = state.costs.farm;
}

function updateSunTheme() {
  const level = getLevel();
  sunWrapper.classList.remove("level-2", "level-3", "level-4");
  if (level >= 4) {
    sunWrapper.classList.add("level-4");
  } else if (level === 3) {
    sunWrapper.classList.add("level-3");
  } else if (level === 2) {
    sunWrapper.classList.add("level-2");
  }
}

function addEnergy(amount) {
  state.energy += amount;
  spawnFloating(amount);
  updateUI();
  saveState();
}

function spawnFloating(amount) {
  const span = document.createElement("span");
  span.textContent = `+${amount}`;
  span.style.left = `${50 + Math.random() * 30 - 15}%`;
  span.style.top = `${50 + Math.random() * 20 - 10}%`;
  floating.appendChild(span);
  setTimeout(() => span.remove(), 900);
}

function handleUpgrade(type) {
  const cost = state.costs[type];
  if (state.energy < cost) {
    return;
  }
  state.energy -= cost;
  if (type === "click") {
    state.clickPower += 1;
    state.costs.click = Math.round(cost * 1.45);
  }
  if (type === "auto") {
    state.autoPower += 1;
    state.costs.auto = Math.round(cost * 1.6);
  }
  if (type === "farm") {
    state.farms += 1;
    state.autoPower += 3;
    state.costs.farm = Math.round(cost * 1.8);
  }
  updateUI();
  saveState();
}

sun.addEventListener("click", () => {
  addEnergy(state.clickPower);
  sun.classList.add("clicked");
  setTimeout(() => sun.classList.remove("clicked"), 150);
});

toggleShop.addEventListener("click", () => {
  shop.classList.toggle("active");
  toggleShop.textContent = shop.classList.contains("active") ? "Скрыть" : "Магазин";
});

upgradeButtons.forEach((button) => {
  button.addEventListener("click", () => handleUpgrade(button.dataset.upgrade));
});

setInterval(() => {
  if (state.autoPower > 0) {
    state.energy += state.autoPower;
    updateUI();
    saveState();
  }
}, 1000);

updateUI();
