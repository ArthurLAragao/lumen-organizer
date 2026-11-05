const button = document.getElementById("copy");
button.addEventListener("click", async () => {
  const status = document.getElementById("copy-status");
  try {
    await navigator.clipboard.writeText(
      document.getElementById("commands").textContent,
    );
    status.textContent =
      "Comandos copiados. Continue a configuração pelo README.";
  } catch {
    status.textContent = "Selecione os comandos acima e copie manualmente.";
  }
});
