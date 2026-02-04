const tg = window.Telegram?.WebApp;

const state = {
  points: 0,
  level: 1,
  clickPower: 1,
  autoClicker: 0,
  farms: 0,
  xp: 0,
  xpToLevel: 100,
};

const elements = {
  points: document.getElementById("points"),
  level: document.getElementById("level"),
  power: document.getElementById("power"),
  xpLabel: document.getElementById("xpLabel"),
  xpBar: document.getElementById("xpBar"),
  sun: document.getElementById("sun"),
  farmBackground: document.getElementById("farmBackground"),
  buyPower: document.getElementById("buyPower"),
  buyAuto: document.getElementById("buyAuto"),
  buyFarm: document.getElementById("buyFarm"),
  powerCost: document.getElementById("powerCost"),
  autoCost: document.getElementById("autoCost"),
  farmCost: document.getElementById("farmCost"),
  saveBtn: document.getElementById("saveBtn"),
};

const costs = {
  power: 30,
  auto: 120,
  farm: 300,
};

const updateUI = () => {
  elements.points.textContent = state.points;
  elements.level.textContent = state.level;
  elements.power.textContent = state.clickPower;
  elements.xpLabel.textContent = `${state.xp} / ${state.xpToLevel}`;
  elements.xpBar.style.width = `${(state.xp / state.xpToLevel) * 100}%`;
  elements.powerCost.textContent = `Стоимость: ${costs.power}`;
  elements.autoCost.textContent = `Стоимость: ${costs.auto}`;
  elements.farmCost.textContent = `Стоимость: ${costs.farm}`;
  renderFarms();
};

const renderFarms = () => {
  elements.farmBackground.innerHTML = "";
  const totalSlots = Math.max(5, state.farms);
  for (let i = 0; i < totalSlots; i += 1) {
    const slot = document.createElement("span");
    slot.textContent = i < state.farms ? "🌻" : "✨";
    elements.farmBackground.appendChild(slot);
  }
};

const gainPoints = (amount) => {
  state.points += amount;
  state.xp += amount;
  if (state.xp >= state.xpToLevel) {
    state.xp -= state.xpToLevel;
    state.level += 1;
    state.xpToLevel = Math.round(state.xpToLevel * 1.25);
  }
  updateUI();
};

const floatText = (text) => {
  const bubble = document.createElement("div");
  bubble.className = "click-float";
  bubble.textContent = text;
  const rect = elements.sun.getBoundingClientRect();
  bubble.style.left = `${rect.left + rect.width / 2}px`;
  bubble.style.top = `${rect.top + rect.height / 2}px`;
  document.body.appendChild(bubble);
  setTimeout(() => bubble.remove(), 1000);
};

const clickSun = () => {
  gainPoints(state.clickPower);
  floatText(`+${state.clickPower}`);
  elements.sun.classList.add("pulse");
  setTimeout(() => elements.sun.classList.remove("pulse"), 150);
};

const attemptPurchase = (type) => {
  if (state.points < costs[type]) {
    return;
  }
  state.points -= costs[type];
  if (type === "power") {
    state.clickPower += 1;
    costs.power = Math.round(costs.power * 1.5);
  }
  if (type === "auto") {
    state.autoClicker += 1;
    costs.auto = Math.round(costs.auto * 1.6);
  }
  if (type === "farm") {
    state.farms += 1;
    costs.farm = Math.round(costs.farm * 1.7);
  }
  updateUI();
};

const setupAutoClicker = () => {
  setInterval(() => {
    if (state.autoClicker > 0) {
      gainPoints(state.autoClicker);
    }
  }, 1500);
};

const saveProgress = async () => {
  const payload = {
    points: state.points,
    level: state.level,
    click_power: state.clickPower,
    auto_clicker: state.autoClicker,
    farms: state.farms,
    user_id: tg?.initDataUnsafe?.user?.id,
  };

  if (tg) {
    tg.sendData(JSON.stringify(payload));
  }

  try {
    await fetch("/api/progress", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    console.error("Save failed", error);
  }
};

const applyTheme = () => {
  if (tg?.colorScheme === "dark") {
    document.body.classList.add("dark");
  }
};

applyTheme();
updateUI();
setupAutoClicker();

if (tg) {
  tg.expand();
}

elements.sun.addEventListener("click", clickSun);
elements.buyPower.addEventListener("click", () => attemptPurchase("power"));
elements.buyAuto.addEventListener("click", () => attemptPurchase("auto"));
elements.buyFarm.addEventListener("click", () => attemptPurchase("farm"));
elements.saveBtn.addEventListener("click", saveProgress);
