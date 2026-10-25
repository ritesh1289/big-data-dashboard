const $ = (id) => document.getElementById(id);

let categoryChart;
let monthlyChart;
let allRecords = [];

async function api(url, options = {}) {
  const response = await fetch(url, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("The server returned an unreadable response.");
  }
  if (!response.ok) throw new Error(data.error || "Request failed.");
  return data;
}

function showMessage(text, isError = false) {
  const message = $("message");
  message.textContent = text;
  message.style.color = isError ? "#b42336" : "#14734b";
  if (isError) message.style.background = "#fff0f1";
  else message.style.background = "";
}

async function loadStatus() {
  const status = $("storageStatus");
  try {
    const data = await api("/api/status");
    status.textContent = `Storage: ${data.storage}`;
    status.title = `${data.hdfs_status} | ${data.hdfs_directory}`;
  } catch {
    status.textContent = "Storage status unavailable";
    status.title = "Could not retrieve storage status.";
  }
}

function renderChart(existingChart, canvasId, type, labels, values, title) {
  if (existingChart) {
    existingChart.data.labels = labels;
    existingChart.data.datasets[0].data = values;
    existingChart.update();
    return existingChart;
  }

  const palette = ["#258b91", "#648cc2", "#e5ae5b", "#9578c8", "#57aa8a", "#df7f74", "#6bafc4"];
  return new Chart($(canvasId), {
    type,
    data: {
      labels,
      datasets: [{
        label: title,
        data: values,
        backgroundColor: type === "doughnut" ? palette : "rgba(37, 139, 145, 0.78)",
        borderColor: type === "doughnut" ? "#ffffff" : "#258b91",
        borderWidth: type === "doughnut" ? 3 : 1,
        borderRadius: type === "bar" ? 5 : 0,
        hoverOffset: type === "doughnut" ? 5 : 0,
        maxBarThickness: 34
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: type === "doughnut" ? "67%" : undefined,
      plugins: {
        legend: {
          position: type === "doughnut" ? "bottom" : "top",
          labels: { usePointStyle: true, pointStyle: "circle", boxWidth: 7, padding: 15, color: "#77869a", font: { size: 10 } }
        },
        tooltip: { displayColors: true }
      },
      scales: type === "bar" ? {
        x: { grid: { display: false }, ticks: { color: "#8795a9", font: { size: 10 } }, border: { display: false } },
        y: { beginAtZero: true, ticks: { precision: 0, color: "#8795a9", font: { size: 10 } }, grid: { color: "#eef2f6" }, border: { display: false } }
      } : {}
    }
  });
}

function addEmptyRow(tbody, columns, text) {
  const row = tbody.insertRow();
  const cell = row.insertCell();
  cell.colSpan = columns;
  cell.textContent = text;
}

function renderPopularBooks(books) {
  const tbody = $("popularBooks");
  tbody.replaceChildren();
  const topBooks = books.slice(0, 5);
  if (!topBooks.length) {
    addEmptyRow(tbody, 4, "No book records available.");
    return;
  }
  topBooks.forEach((book, index) => {
    const row = tbody.insertRow();
    row.insertCell().textContent = String(index + 1).padStart(2, "0");
    row.insertCell().textContent = book.book_id;
    row.insertCell().textContent = book.book_title;
    row.insertCell().textContent = book.borrow_count;
  });
}

function renderRecords() {
  const query = $("search").value.trim().toLowerCase();
  const tbody = $("recordsTable");
  tbody.replaceChildren();
  const filtered = allRecords.filter((record) =>
    Object.values(record).some((value) => String(value).toLowerCase().includes(query))
  );
  if (!filtered.length) {
    addEmptyRow(tbody, 5, "No matching borrowing records.");
    return;
  }
  filtered.forEach((record) => {
    const row = tbody.insertRow();
    ["record_id", "book_title", "category", "student_id", "borrow_date"].forEach((key) => {
      row.insertCell().textContent = record[key] ?? "";
    });
  });
}

async function refreshDashboard() {
  const data = await api("/api/analytics");
  $("totalRecords").textContent = data.total_records;
  $("uniqueBooks").textContent = data.unique_books;
  $("uniqueStudents").textContent = data.unique_students;
  $("uniqueCategories").textContent = data.unique_categories;

  categoryChart = renderChart(categoryChart, "categoryChart", "doughnut", data.categories.labels, data.categories.values, "Borrowings");
  monthlyChart = renderChart(monthlyChart, "monthlyChart", "bar", data.monthly.labels, data.monthly.values, "Monthly borrowings");
  renderPopularBooks(data.popular_books);
  allRecords = data.records;
  renderRecords();
}

$("search").addEventListener("input", renderRecords);
$("csvFile").addEventListener("change", (event) => {
  $("fileName").textContent = event.target.files[0]?.name || "Choose a CSV file";
});

$("uploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("csvFile").files[0];
  if (!file) {
    showMessage("Please select a CSV file.", true);
    return;
  }

  const button = $("uploadButton");
  button.disabled = true;
  button.textContent = "Uploading...";
  try {
    const form = new FormData();
    form.append("file", file);
    const result = await api("/api/upload", { method: "POST", body: form });
    showMessage(`${result.message}${result.hdfs_saved ? " Dataset also saved to HDFS." : " Dataset saved locally; HDFS was not updated."}`);
    $("csvFile").value = "";
    $("fileName").textContent = "Choose a CSV file";
    await refreshDashboard();
    await loadStatus();
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    button.disabled = false;
    button.innerHTML = 'Upload and analyze <span aria-hidden="true">→</span>';
  }
});

async function startDashboard() {
  await loadStatus();
  try {
    await refreshDashboard();
  } catch (error) {
    showMessage(error.message, true);
  }
}

startDashboard();
