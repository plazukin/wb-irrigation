const relayRequests = new Map();

async function relayLoadJson(url) {
  if (!relayRequests.has(url)) {
    relayRequests.set(url, fetch(url).then((response) => {
      if (!response.ok) throw new Error();
      return response.json();
    }));
  }
  return relayRequests.get(url);
}

function relayFillSelect(select, items, placeholder, selected) {
  select.replaceChildren(new Option(placeholder, ""));
  for (const item of items) select.add(new Option(`${item.title} (${item.id})`, item.id));
  if (selected && !items.some((item) => item.id === selected)) select.add(new Option(`${selected} (недоступно)`, selected));
  select.value = selected || "";
}

async function relayLoadControls(form, selected = "") {
  const device = form.elements.relay_device_id.value;
  const control = form.elements.relay_control_id;
  if (!device) return relayFillSelect(control, [], "Сначала выберите устройство", "");
  try {
    const url = new URL(form.dataset.controlsUrl, window.location.href);
    url.searchParams.set("device_id", device);
    const data = await relayLoadJson(url.toString());
    relayFillSelect(control, data.controls, "Выберите канал", selected);
  } catch {
    relayFillSelect(control, [], "Не удалось загрузить каналы", selected);
  }
}

function relaySetMode(form) {
  const basic = form.querySelector(".relay-basic");
  const manual = form.querySelector(".relay-manual");
  const basicMode = form.querySelector(".relay-mode").value === "basic";
  basic.hidden = !basicMode;
  manual.hidden = basicMode;
  for (const field of basic.querySelectorAll("input,select")) field.disabled = !basicMode;
  for (const field of manual.querySelectorAll("input,select")) field.disabled = basicMode;
}

async function relayProbe(form, kind) {
  const data = Object.fromEntries(new FormData(form));
  const body = {relay_device_id:data.relay_device_id||null,relay_control_id:data.relay_control_id||null,relay_state_topic:data.relay_state_topic||null,relay_set_topic:data.relay_set_topic||null};
  const result = form.querySelector(".probe-result");
  result.textContent = "Проверка…";
  try {
    const response = await fetch(kind === "test" ? form.dataset.testUrl : form.dataset.validateUrl, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    result.textContent = JSON.stringify(await response.json(), null, 2);
  } catch {
    result.textContent = "Не удалось выполнить запрос";
  }
}

for (const form of document.querySelectorAll(".relay-form")) {
  const device = form.elements.relay_device_id;
  const control = form.elements.relay_control_id;
  relayLoadJson(form.dataset.devicesUrl).then((data) => {
    relayFillSelect(device, data.devices, "Выберите устройство", device.dataset.selected);
    relayLoadControls(form, control.dataset.selected);
  }).catch(() => relayFillSelect(device, [], "Не удалось загрузить устройства", device.dataset.selected));
  device.addEventListener("change", () => relayLoadControls(form));
  form.querySelector(".relay-mode").addEventListener("change", () => relaySetMode(form));
  for (const button of form.querySelectorAll("[data-probe]")) button.addEventListener("click", () => relayProbe(form, button.dataset.probe));
  relaySetMode(form);
}
