const svg = document.querySelector("#floorPlan");
const status = document.querySelector("#viewStatus");
const buttons = [...document.querySelectorAll("[data-view]")];
const isEmbed = new URLSearchParams(window.location.search).get("embed") === "1";
const views = {
  all: {
    box: isEmbed ? "0 70 1380 820" : "0 0 1380 1180",
    status: "4층 공통틀 위에 3203 라인 입구, 자유공간, 증축부 복도, IT홀, 3104-1·2를 함께 표시하고 있습니다."
  },
  extension: {
    box: "720 80 630 660",
    status: "3203 라인에서 열린 첫 입구로 자유공간에 들어가고, 뒤쪽 증축부 복도를 통해 IT홀과 3104-1·2로 이어집니다."
  },
  core: {
    box: "540 600 360 430",
    status: "4층 기준으로 유지되는 중앙 코어와 코어복도를 확대했습니다."
  }
};

function setView(name) {
  const view = views[name];
  svg.setAttribute("viewBox", view.box);
  if (status) status.textContent = view.status;
  buttons.forEach((button) => {
    const active = button.dataset.view === name;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

buttons.forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
setView("all");
