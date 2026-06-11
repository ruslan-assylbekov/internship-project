/* ============================================================
   WEATHER
   ============================================================ */

/**
 * Called when the user clicks "Get Weather".
 * Reads city + days from the form, calls your FastAPI backend,
 * then updates the result section on the page.
 */
async function getWeather() {
  const city    = document.getElementById("city").value.trim();
  const days    = document.getElementById("days").value.trim();
  const result  = document.getElementById("weather-result");
  const errorEl = document.getElementById("weather-error");

  // Hide any previous result / error
  result.classList.remove("visible");
  errorEl.classList.remove("visible");

  if (!city) return;

  try {
    const response = await fetch(`http://127.0.0.1:8000/weather/${city}/${days || 1}`);

    if (!response.ok) throw new Error("API returned an error");

    const data = await response.json();

    // Fill in the result fields
    document.getElementById("temp").innerHTML    = `${data.temperature}<sup>°C</sup>`;
    document.getElementById("city-name").textContent = data.city;
    document.getElementById("feels").textContent     = `${data.feeling}°C`;
    document.getElementById("sky-val").textContent   = data.clouds;
    document.getElementById("forecast").textContent  = data.forecast;

    // Show the result section
    result.classList.add("visible");

  } catch (error) {
    // Show the error message
    errorEl.classList.add("visible");
    console.error("Weather fetch failed:", error);
  }
}

// Also trigger on Enter key inside the city input
document.getElementById("city").addEventListener("keydown", function (event) {
  if (event.key === "Enter") getWeather();
});


/* ============================================================
   BOOK BORROWING
   ============================================================ */

/**
 * Placeholder for all book actions.
 * Replace the alert() with a real fetch() call to your borrowing API.
 *
 * @param {string} action  One of: 'borrow' | 'return' | 'browse' | 'reserve' | 'report'
 */
async function bookAction(action) {
 
  console.log("Book action triggered:", action);
  if (action === "browse"){
    const response = await fetch("http://127.0.0.1:8000/books");
    const data = await response.json();
    document.getElementById("books-result").textContent = JSON.stringify(data, null, 2);
  }
    if (action === "borrow"){
    const response = await fetch(`http://127.0.0.1:8000/books/${action}`);
    const data = await response.json();
    document.getElementById("books-result").textContent = JSON.stringify(data, null, 2);
    }
  //alert(`Action: "${action}" — connect this button to your book borrowing API.`);
}

async function addBook() {
    const body = {
          title: document.getElementById("b-title").value,
          author:  document.getElementById("b-author").value,
          year:     document.getElementById("b-year").value,
      };

    const response  = await fetch(`http://127.0.0.1:8000/books`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }, // ?
      body:   JSON.stringify(body),
    });
}



/* ============================================================
   USERS
   ============================================================ */

async function testGetAllUsers() {
    const response = await fetch("http://127.0.0.1:8000/users");
    const data = await response.json();
    document.getElementById("users-result").textContent = JSON.stringify(data, null, 2);
}


async function testCreateUser() {
    const body = {
        firstname: document.getElementById("u-firstname").value,
        lastname:  document.getElementById("u-lastname").value,
        email:     document.getElementById("u-email").value,
        password:  document.getElementById("u-password").value,
    };

    const response = await fetch("http://127.0.0.1:8000/users", {
        method:  "POST",
        headers: { "Content-Type": "application/json" }, // ?
        body:    JSON.stringify(body),
    });
}


async function testDeleteUser() {
    const user_id = document.getElementById("u-delete-id").value;
    if (!user_id) return alert("Enter a user ID first");
    const response = await fetch(`http://127.0.0.1:8000/users/${user_id}`, {method: "DELETE", });
}


