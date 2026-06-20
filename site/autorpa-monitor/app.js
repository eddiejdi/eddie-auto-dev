const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

const savingsForm = document.querySelector("#savingsCalc");
const hoursInput = document.querySelector("#hoursInput");
const rateInput = document.querySelector("#rateInput");
const calcResult = document.querySelector("#calcResult");
const leadForm = document.querySelector("#leadForm");
const formNote = document.querySelector("#formNote");
const businessWhatsApp = "5511981193899";

function updateSavings() {
  const weeklyHours = Number(hoursInput.value || 0);
  const hourlyRate = Number(rateInput.value || 0);
  const monthlySavings = weeklyHours * hourlyRate * 4;
  calcResult.value = `${currency.format(monthlySavings)}/mês`;
}

function sanitizePhone(value) {
  return value.replace(/\D/g, "");
}

function buildLeadMessage(formData) {
  return [
    "Olá, quero solicitar uma avaliação de automação.",
    "",
    `Nome: ${formData.get("name")}`,
    `Empresa: ${formData.get("company")}`,
    `WhatsApp: ${formData.get("phone")}`,
    `Gargalo principal: ${formData.get("pain")}`,
    "",
    "Quero avaliar qual rotina pode ser automatizada ou monitorada primeiro.",
  ].join("\n");
}

hoursInput.addEventListener("input", updateSavings);
rateInput.addEventListener("input", updateSavings);
savingsForm.addEventListener("submit", (event) => event.preventDefault());

leadForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const formData = new FormData(leadForm);
  const message = buildLeadMessage(formData);
  const phone = sanitizePhone(formData.get("phone") || "");

  localStorage.setItem(
    "autorpa:lastLead",
    JSON.stringify({
      name: formData.get("name"),
      company: formData.get("company"),
      phone,
      pain: formData.get("pain"),
      createdAt: new Date().toISOString(),
    }),
  );

  formNote.classList.add("success");
  formNote.textContent =
    "Mensagem criada. Redirecionando para o WhatsApp nesta mesma aba.";

  const encoded = encodeURIComponent(message);
  window.location.href = `https://wa.me/${businessWhatsApp}?text=${encoded}`;
});

updateSavings();
