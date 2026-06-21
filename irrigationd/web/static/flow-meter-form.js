const flowMeterForm = document.querySelector(".flow-meter-form");

if (flowMeterForm) {
  const mode = flowMeterForm.querySelector(".flow-meter-mode");
  const basic = flowMeterForm.querySelector(".flow-meter-basic");
  const manual = flowMeterForm.querySelector(".flow-meter-manual");
  const device = flowMeterForm.elements.device_id;
  const control = flowMeterForm.elements.control_id;

  function fill(select, items, placeholder, selected) {
    select.replaceChildren(new Option(placeholder, ""));
    for (const item of items) select.add(new Option(`${item.title} (${item.id})`, item.id));
    if (selected && !items.some((item) => item.id === selected)) select.add(new Option(`${selected} (недоступно)`, selected));
    select.value = selected || "";
  }

  async function loadControls(selected = "") {
    if (!device.value) return fill(control, [], "Сначала выберите устройство", "");
    try {
      const url = new URL(flowMeterForm.dataset.controlsUrl, window.location.href);
      url.searchParams.set("device_id", device.value);
      const response = await fetch(url);
      if (!response.ok) throw new Error();
      fill(control, (await response.json()).controls, "Выберите канал", selected);
    } catch {
      fill(control, [], "Не удалось загрузить каналы", selected);
    }
  }

  function setMode() {
    const basicMode = mode.value === "basic";
    basic.hidden = !basicMode;
    manual.hidden = basicMode;
    for (const field of basic.querySelectorAll("input,select")) field.disabled = !basicMode;
    for (const field of manual.querySelectorAll("input,select")) field.disabled = basicMode;
  }

  fetch(flowMeterForm.dataset.devicesUrl).then((response) => {
    if (!response.ok) throw new Error();
    return response.json();
  }).then((data) => {
    fill(device, data.devices, "Выберите устройство", device.dataset.selected);
    loadControls(control.dataset.selected);
  }).catch(() => fill(device, [], "Не удалось загрузить устройства", device.dataset.selected));

  device.addEventListener("change", () => loadControls());
  mode.addEventListener("change", setMode);
  setMode();
}
