/* ============================================================
   CONFIG
   ============================================================ */

// FastAPI serves this page at "/", so relative paths are same-origin and need
// no host. Only a page opened straight off disk (file://) has to be told where
// the API lives.
const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";

// Both list endpoints cap limit at 100; asking for the default keeps the two
// tables in step with what the API considers a page.
const PAGE_LIMIT = 50;

// localStorage rather than a variable: the session has to survive a refresh.
const TOKEN_KEY = "library-token";

// Mirrors UserCreate.password so the obvious mistake is caught before the
// request instead of coming back as a 422 the user has to decode.
const MIN_PASSWORD_LENGTH = 8;

// Any other borrowing state no longer ties up a book, so it is history and has
// nothing left to return or report.
const OPEN_BORROWING_STATES = ["Active", "Reserved"];

const ADD_BOOK_FIELDS = ["b-title", "b-author", "b-year"];

/* ------------------------------------------------------------
   View state

   The last responses are cached because signing in or out changes what the
   per-row buttons may do, and redrawing beats re-fetching for that. `null`
   means "not loaded yet", which is why it is distinct from an empty list.
   ------------------------------------------------------------ */
let currentUser  = null;
let catalogue    = null;
let myBorrowings = null;


/* ============================================================
   HTTP
   ============================================================ */

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function isSignedIn() {
  return Boolean(getToken());
}

function jsonRequest(method, body) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

/**
 * FastAPI answers 422 with a list of {loc, msg} objects. Dumping that as JSON
 * is unreadable, so the field name and message are pulled out instead.
 */
function describeDetail(detail) {
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const path  = Array.isArray(item.loc) ? item.loc : [];
        const field = path[path.length - 1];
        return field && field !== "body" ? `${field}: ${item.msg}` : item.msg;
      })
      .join("; ");
  }

  return JSON.stringify(detail);
}

/**
 * Wrapper around fetch that raises on non-2xx and surfaces FastAPI's
 * error body. The previous code ignored response status entirely, so a
 * failed POST looked identical to a successful one.
 *
 * It also owns the bearer token: attaching it here means no caller can forget,
 * and a 401 is handled once rather than at every call site.
 */
async function apiFetch(path, options = {}) {
  const token   = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (response.status === 401 && token) {
    // The token expired or the account is gone. Keeping it would make every
    // later click fail identically, so the session is dropped and the UI falls
    // back to its signed-out state before the error surfaces.
    endSession();
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body.detail) detail = describeDetail(body.detail);
    } catch {
      /* response had no JSON body; keep the status-based message */
    }
    throw new Error(detail);
  }

  // 204 carries no body, and DELETE /books/{id} returns exactly that.
  // response.json() would throw on the empty string.
  if (response.status === 204) return null;
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}


/* ============================================================
   SMALL DOM HELPERS
   ============================================================ */

function showError(elementId, message) {
  const element = document.getElementById(elementId);
  element.textContent = message;
  element.classList.add("visible");
}

function clearError(elementId) {
  document.getElementById(elementId).classList.remove("visible");
}

function setVisible(elementId, visible) {
  document.getElementById(elementId).classList.toggle("visible", visible);
}

// textContent, never innerHTML: titles, author names and emails come from the
// API and would otherwise be parsed as markup.
function cell(text, className = "") {
  const td = document.createElement("td");
  if (className) td.className = className;
  td.textContent = text;
  return td;
}

function statusCell(status) {
  const td = document.createElement("td");
  td.appendChild(stamp(status));
  return td;
}

/**
 * A status rendered as an ink impression. Both API vocabularies
 * (BookStatus and BorrowingStatus) are single words, so the value doubles as
 * the class that colours the stamp.
 */
function stamp(status, extraClass = "") {
  const element = document.createElement("span");
  element.className = `stamp ${String(status).toLowerCase()} ${extraClass}`.trim();
  element.textContent = status;
  return element;
}

function actionButton(label, variant, { onClick, disabled = false, hint = "" }) {
  const button = document.createElement("button");
  button.className = `btn-sm ${variant}`.trim();
  button.textContent = label;
  button.disabled = disabled;
  // Explain the greyed-out button rather than leaving the user to guess.
  if (disabled && hint) button.title = hint;
  button.addEventListener("click", onClick);
  return button;
}

function actionsCell(buttons) {
  const td   = document.createElement("td");
  const wrap = document.createElement("div");
  wrap.className = "row-actions";
  buttons.forEach((button) => wrap.appendChild(button));
  td.appendChild(wrap);
  return td;
}

function placeholderRow(columnCount, message) {
  const row  = document.createElement("tr");
  const td   = document.createElement("td");
  td.colSpan   = columnCount;
  td.className = "empty-state";
  td.textContent = message;
  row.appendChild(td);
  return row;
}

/** The same empty state for the card grid, which has no columns to span. */
function placeholderCard(message) {
  const element = document.createElement("p");
  element.className = "empty-state";
  element.textContent = message;
  // The grid is auto-fill, so an unspanned note would sit in one narrow column.
  element.style.gridColumn = "1 / -1";
  return element;
}

/**
 * Reservations have no due date, hence the dash. The API sends naive UTC, so
 * the value is rendered as it arrived instead of being shifted into the
 * browser's timezone and possibly landing on the wrong day.
 */
function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleDateString(undefined, {
    year: "numeric", month: "short", day: "numeric",
  });
}

/**
 * Whole days from today until a due date; negative once it has passed.
 *
 * Compared by calendar day rather than by instant, for the same reason the
 * date is rendered offset-free: the API sends naive UTC, so an hours-precise
 * comparison would call a book late a few hours early or late depending on the
 * reader's timezone. A book due today is not yet overdue.
 */
function daysUntil(value) {
  if (!value) return null;

  const due = new Date(value);
  if (Number.isNaN(due.getTime())) return null;

  const startOfDue = new Date(due.getFullYear(), due.getMonth(), due.getDate());
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  return Math.round((startOfDue - startOfToday) / 86400000);
}

/** "3 days overdue" / "due tomorrow" — plain, and specific about the count. */
function describeDue(days) {
  if (days === null) return "";
  if (days < -1) return `${Math.abs(days)} days overdue`;
  if (days === -1) return "1 day overdue";
  if (days === 0) return "Due today";
  if (days === 1) return "Due tomorrow";
  return `${days} days left`;
}


/* ============================================================
   AUTH
   ============================================================ */

function startSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  currentUser  = user;
  // Whatever was on screen belonged to nobody; the new owner's list is unknown
  // until fetched.
  myBorrowings = null;
  renderAuthState();
}

function endSession() {
  localStorage.removeItem(TOKEN_KEY);
  currentUser  = null;
  myBorrowings = null;
  renderAuthState();
}

/**
 * Single place that reflects "do we hold a token?" in the UI. Everything that
 * needs one is disabled without it, with a hint saying so, because letting the
 * call 401 is a worse way to find out.
 */
function renderAuthState() {
  const signedIn = isSignedIn();

  setVisible("auth-forms", !signedIn);
  setVisible("auth-signed-in", signedIn);

  if (currentUser) {
    document.getElementById("auth-user-name").textContent =
      `${currentUser.firstname} ${currentUser.lastname}`;
    // The account's own id, padded the way a card number is printed. Data, not
    // decoration -- it is what /users/{id} answers to.
    document.getElementById("borrower-no").textContent =
      `No. ${String(currentUser.id).padStart(5, "0")}`;
  }

  ADD_BOOK_FIELDS.forEach((id) => {
    document.getElementById(id).disabled = !signedIn;
  });
  document.getElementById("add-book-btn").disabled = !signedIn;
  document.getElementById("refresh-borrowings-btn").disabled = !signedIn;

  setVisible("add-book-hint", !signedIn);
  setVisible("borrow-auth-hint", !signedIn);

  // The per-row buttons depend on auth, so both views are redrawn from cache.
  renderCatalogue();
  renderBorrowings();
  renderLoanCount();
}

/** How many books the ticket holder currently has out. */
function renderLoanCount() {
  const element = document.getElementById("borrower-count");
  if (!element) return;

  const open = (myBorrowings || []).filter((row) =>
    OPEN_BORROWING_STATES.includes(row.status)
  );
  element.textContent = String(open.length);
}

/**
 * Exchange credentials for a token. /auth/login returns the user alongside it,
 * so no follow-up request is needed to render the profile.
 */
async function authenticate(email, password) {
  const session = await apiFetch("/auth/login", jsonRequest("POST", { email, password }));
  startSession(session.access_token, session.user);
  await loadBorrowings();
}

async function signIn() {
  clearError("login-error");

  const email    = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;

  if (!email || !password) {
    showError("login-error", "Email and password are required.");
    return;
  }

  try {
    await authenticate(email, password);
    document.getElementById("login-password").value = "";
  } catch (error) {
    showError("login-error", error.message);
  }
}

async function register() {
  clearError("reg-error");

  const email    = document.getElementById("reg-email").value.trim();
  const password = document.getElementById("reg-password").value;
  const body = {
    firstname: document.getElementById("reg-firstname").value.trim(),
    lastname:  document.getElementById("reg-lastname").value.trim(),
    email,
    password,
  };

  if (!body.firstname || !body.lastname || !email) {
    showError("reg-error", "First name, last name and email are required.");
    return;
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    showError("reg-error", `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
    return;
  }

  try {
    await apiFetch("/users/", jsonRequest("POST", body));
    // POST /users/ only creates the row -- the token comes from a login -- so
    // the new account is signed in here instead of asking for it all again.
    await authenticate(email, password);
    document.getElementById("reg-password").value = "";
  } catch (error) {
    showError("reg-error", error.message);
  }
}

function signOut() {
  endSession();
  clearError("books-error");
}


/* ============================================================
   WEATHER
   ============================================================ */

/**
 * Called when the user clicks "Get Weather".
 * Reads the city from the form, calls the backend, then updates the page.
 */
async function getWeather() {
  const city   = document.getElementById("city").value.trim();
  const result = document.getElementById("weather-result");

  // Hide any previous result / error
  result.classList.remove("visible");
  clearError("weather-error");

  if (!city) return;

  try {
    // GET /weather/{city} returns current conditions only.
    const data = await apiFetch(`/weather/${encodeURIComponent(city)}`);

    document.getElementById("temp").innerHTML        = `${data.temperature}<sup>°C</sup>`;
    document.getElementById("city-name").textContent = data.city;
    document.getElementById("feels").textContent     = `${data.feeling}°C`;
    document.getElementById("sky-val").textContent   = data.clouds;

    result.classList.add("visible");

  } catch (error) {
    showError("weather-error", error.message);
    console.error("Weather fetch failed:", error);
  }
}


/* ============================================================
   BOOKS — catalogue
   ============================================================ */

function renderCatalogue() {
  const body = document.getElementById("catalogue-list");
  body.textContent = "";

  if (catalogue === null) {
    body.appendChild(placeholderRow(5, "Loading catalogue…"));
    return;
  }
  if (catalogue.length === 0) {
    body.appendChild(placeholderRow(5, "No books match this search."));
    return;
  }

  const signedIn = isSignedIn();

  catalogue.forEach((book) => {
    const row = document.createElement("tr");
    // Classed so the stylesheet can set the column widths and give the author
    // and year their own treatment; an unclassed cell inherits none of it.
    row.appendChild(cell(book.title, "title"));
    row.appendChild(cell(book.author, "author"));
    row.appendChild(cell(book.year, "year"));
    row.appendChild(statusCell(book.status));

    // Borrow and reserve both require the book to be free, and both endpoints
    // take a book_id -- so the row carries the buttons and the id never has to
    // be typed. A 409 for an unavailable book becomes a disabled button.
    const available = book.status === "Available";
    const blocked   = !signedIn
      ? "Sign in to borrow"
      : `This book is ${String(book.status).toLowerCase()}`;

    row.appendChild(actionsCell([
      actionButton("Borrow", "primary", {
        onClick:  () => bookAction("borrow", book.id),
        disabled: !signedIn || !available,
        hint:     blocked,
      }),
      actionButton("Reserve", "", {
        onClick:  () => bookAction("reserve", book.id),
        disabled: !signedIn || !available,
        hint:     blocked,
      }),
      actionButton("Remove", "danger", {
        onClick:  () => bookAction("delete", book.id),
        disabled: !signedIn,
        hint:     "Sign in to edit the catalogue",
      }),
    ]));

    body.appendChild(row);
  });
}

async function loadCatalogue() {
  const params = new URLSearchParams({ skip: "0", limit: String(PAGE_LIMIT) });

  // Empty values are left out rather than sent blank: q declares min_length=1
  // and "" is not a member of the status enum, so either would be a 422.
  const query = document.getElementById("book-search").value.trim();
  if (query) params.set("q", query);

  const status = document.getElementById("book-status-filter").value;
  if (status) params.set("status", status);

  // Trailing slash kept before the query string -- /books without it is a 307
  // redirect, which some browsers strip CORS headers from.
  catalogue = await apiFetch(`/books/?${params.toString()}`);
  renderCatalogue();
}

async function addBook() {
  clearError("book-error");

  const title  = document.getElementById("b-title").value.trim();
  const author = document.getElementById("b-author").value.trim();
  const year   = document.getElementById("b-year").value;

  if (!title || !author) {
    showError("book-error", "Title and author are required.");
    return;
  }
  if (year === "") {
    showError("book-error", "Year is required.");
    return;
  }

  try {
    // The input yields a string; the API expects an int.
    await apiFetch("/books/", jsonRequest("POST", { title, author, year: Number(year) }));

    ADD_BOOK_FIELDS.forEach((id) => {
      document.getElementById(id).value = "";
    });
    await loadCatalogue();
  } catch (error) {
    showError("book-error", error.message);
  }
}


/* ============================================================
   BOOKS — borrowings
   ============================================================ */

/**
 * One date-due card per open loan, after the pocket card in the back of a
 * library book: title typed along the top, return date stamped below it.
 */
function dueBlock(borrowing) {
  const block = document.createElement("div");
  block.className = "due-block";

  const eyebrow = document.createElement("span");
  eyebrow.className = "due-eyebrow";

  const date = document.createElement("span");
  date.className = "due-date";

  // A reservation is a hold, so there is nothing due back yet. Saying "—" in a
  // DATE DUE box would read as missing data rather than as not applicable.
  if (!borrowing.due_date) {
    block.classList.add("is-hold");
    eyebrow.textContent = "On hold";
    date.textContent = "Not yet due";
  } else {
    const days = daysUntil(borrowing.due_date);
    if (days !== null && days < 0) block.classList.add("is-overdue");
    eyebrow.textContent = "Date due";
    date.textContent = formatDate(borrowing.due_date);
  }

  block.appendChild(eyebrow);
  block.appendChild(date);
  return block;
}

function dueCard(borrowing) {
  const card = document.createElement("article");
  card.className = "due-card";

  const heading = document.createElement("div");
  // The nested book is what makes a title renderable without a second
  // request; the id is the fallback if it ever comes back null.
  const title = document.createElement("h3");
  title.className = "due-card-title";
  title.textContent = borrowing.book
    ? borrowing.book.title
    : `Book #${borrowing.book_id}`;
  heading.appendChild(title);

  if (borrowing.book && borrowing.book.author) {
    const author = document.createElement("p");
    author.className = "due-card-author";
    author.textContent = borrowing.book.author;
    heading.appendChild(author);
  }
  card.appendChild(heading);

  card.appendChild(dueBlock(borrowing));

  // Only stated when it carries news: a countdown on every card is noise, a
  // day count on a late one is the reason to act.
  const days = daysUntil(borrowing.due_date);
  if (days !== null && days <= 1) {
    const note = document.createElement("p");
    note.className = "due-note";
    note.textContent = describeDue(days);
    card.appendChild(note);
  }

  const foot = document.createElement("div");
  foot.className = "due-card-foot";
  foot.appendChild(stamp(borrowing.status));

  // Return and report-lost act on a borrowing_id, which only this view has.
  const actions = document.createElement("div");
  actions.className = "row-actions";
  actions.appendChild(actionButton("Return", "primary", {
    onClick: () => bookAction("return", borrowing.id),
  }));
  actions.appendChild(actionButton("Report lost", "danger", {
    onClick: () => bookAction("report", borrowing.id),
  }));
  foot.appendChild(actions);

  card.appendChild(foot);
  return card;
}

function renderBorrowings() {
  const body = document.getElementById("book-list");
  body.textContent = "";

  if (!isSignedIn()) {
    body.appendChild(placeholderCard("Register or sign in to take a book out."));
    return;
  }
  if (myBorrowings === null) {
    body.appendChild(placeholderCard("Fetching your loans…"));
    return;
  }

  // /borrowings/me returns the whole history; only open rows can still be
  // returned or reported, so the closed ones would be dead weight here.
  const open = myBorrowings.filter((row) => OPEN_BORROWING_STATES.includes(row.status));

  if (open.length === 0) {
    body.appendChild(placeholderCard("Nothing on loan. Borrow something from the catalogue below."));
    return;
  }

  // Soonest due first, so anything late or nearly late is read first. Holds
  // have no date and sort to the end.
  const ordered = [...open].sort((a, b) => {
    if (!a.due_date) return 1;
    if (!b.due_date) return -1;
    return new Date(a.due_date) - new Date(b.due_date);
  });

  ordered.forEach((borrowing) => body.appendChild(dueCard(borrowing)));
}

async function loadBorrowings() {
  if (!isSignedIn()) {
    myBorrowings = null;
    renderBorrowings();
    return;
  }

  myBorrowings = await apiFetch(`/borrowings/me?skip=0&limit=${PAGE_LIMIT}`);
  renderBorrowings();
  renderLoanCount();
}

/**
 * Every mutation moves a book between shelves -- borrow makes it Borrowed,
 * return puts it back to Available, reserve holds it, report-lost writes it
 * off -- so both tables are reloaded rather than patched locally.
 */
async function refreshLibrary() {
  await loadCatalogue();
  await loadBorrowings();
}

/**
 * The one entry point the panel's buttons call. Ids come from the row that was
 * clicked, so "borrow"/"reserve" carry a book_id and "return"/"report" carry a
 * borrowing_id.
 */
async function bookAction(action, id) {
  clearError("books-error");

  // The buttons are already disabled without a token; this guards the same
  // rule for anything else reaching this global.
  if (action !== "browse" && !isSignedIn()) {
    showError("books-error", "Sign in first.");
    return;
  }

  try {
    switch (action) {
      case "browse":
        await loadCatalogue();
        break;

      case "mine":
        await loadBorrowings();
        break;

      case "borrow":
        await apiFetch("/borrowings/borrow", jsonRequest("POST", { book_id: id }));
        await refreshLibrary();
        break;

      case "reserve":
        await apiFetch("/borrowings/reserve", jsonRequest("POST", { book_id: id }));
        await refreshLibrary();
        break;

      case "return":
        await apiFetch(`/borrowings/${id}/return`, { method: "POST" });
        await refreshLibrary();
        break;

      case "report":
        await apiFetch(`/borrowings/${id}/report-lost`, { method: "POST" });
        await refreshLibrary();
        break;

      case "delete":
        // Irreversible and one click away, so it is confirmed first.
        if (!window.confirm("Delete this book from the catalogue?")) return;
        await apiFetch(`/books/${id}`, { method: "DELETE" });
        await refreshLibrary();
        break;

      default:
        showError("books-error", `Unknown action "${action}".`);
    }
  } catch (error) {
    showError("books-error", error.message);
  }
}


/* ============================================================
   EVENTS & STARTUP
   ============================================================ */

// Enter submits, so none of these forms needs its button to be reachable.
function submitOnEnter(elementIds, handler) {
  elementIds.forEach((id) => {
    document.getElementById(id).addEventListener("keydown", (event) => {
      if (event.key === "Enter") handler();
    });
  });
}

submitOnEnter(["city"], getWeather);
submitOnEnter(["login-email", "login-password"], signIn);
submitOnEnter(["reg-firstname", "reg-lastname", "reg-email", "reg-password"], register);
submitOnEnter(["book-search"], () => bookAction("browse"));

// A filter change is itself the request to re-query; a second click on Browse
// would be busywork.
document.getElementById("book-status-filter")
  .addEventListener("change", () => bookAction("browse"));

/**
 * A stored token is verified rather than trusted -- it may have expired while
 * the tab was closed -- and apiFetch clears it if /users/me answers 401, which
 * leaves the page in its signed-out state.
 */
async function start() {
  renderAuthState();

  if (isSignedIn()) {
    try {
      currentUser = await apiFetch("/users/me");
      renderAuthState();
    } catch (error) {
      console.warn("Stored session rejected:", error.message);
    }
  }

  try {
    await loadCatalogue();
  } catch (error) {
    showError("books-error", `Failed to load the catalogue: ${error.message}`);
  }

  try {
    await loadBorrowings();
  } catch (error) {
    showError("books-error", `Failed to load your borrowings: ${error.message}`);
  }
}

start();
