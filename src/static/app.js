document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const messageDiv = document.getElementById("message");
  const accountButton = document.getElementById("account-button");
  const accountMenu = document.getElementById("account-menu");
  const loginDialog = document.getElementById("login-dialog");
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  let teacher = null;

  function showMessage(message, type) {
    messageDiv.textContent = message;
    messageDiv.className = type;
  }

  function setTeacher(username) {
    teacher = username;
    document.getElementById("account-name").textContent = username || "";
    document.getElementById("login-button").classList.toggle("hidden", !!username);
    document.getElementById("logout-button").classList.toggle("hidden", !username);
    document.getElementById("signup-container").classList.toggle("hidden", !username);
  }

  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const activities = await response.json();
      const selectedActivity = activitySelect.value;
      activitiesList.replaceChildren();
      activitySelect.replaceChildren(new Option("-- Select an activity --", ""));

      Object.entries(activities).forEach(([name, details]) => {
        const card = document.createElement("div");
        card.className = "activity-card";
        const heading = document.createElement("h4");
        heading.textContent = name;
        card.appendChild(heading);
        for (const text of [
          details.description,
          `Schedule: ${details.schedule}`,
          `Availability: ${details.max_participants - details.participants.length} spots left`,
        ]) {
          const paragraph = document.createElement("p");
          paragraph.textContent = text;
          card.appendChild(paragraph);
        }
        const participants = document.createElement("div");
        participants.className = "participants-container";
        if (details.participants.length) {
          const section = document.createElement("div");
          section.className = "participants-section";
          const title = document.createElement("h5");
          title.textContent = "Participants:";
          const list = document.createElement("ul");
          list.className = "participants-list";
          details.participants.forEach((email) => {
            const item = document.createElement("li");
            const label = document.createElement("span");
            label.className = "participant-email";
            label.textContent = email;
            item.appendChild(label);
            if (teacher) {
              const button = document.createElement("button");
              button.className = "delete-btn";
              button.type = "button";
              button.textContent = "❌";
              button.setAttribute("aria-label", `Unregister ${email} from ${name}`);
              button.addEventListener("click", () => changeRegistration(name, email, "DELETE"));
              item.appendChild(button);
            }
            list.appendChild(item);
          });
          section.append(title, list);
          participants.appendChild(section);
        } else {
          const empty = document.createElement("p");
          empty.textContent = "No participants yet";
          participants.appendChild(empty);
        }
        card.appendChild(participants);
        activitiesList.appendChild(card);
        activitySelect.add(new Option(name, name));
      });
      activitySelect.value = selectedActivity;
    } catch (error) {
      activitiesList.textContent = "Failed to load activities. Please try again later.";
      console.error("Error fetching activities:", error);
    }
  }

  async function changeRegistration(activity, email, method) {
    const action = method === "POST" ? "signup" : "unregister";
    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(activity)}/${action}?email=${encodeURIComponent(email)}`,
        { method }
      );
      const result = await response.json();
      if (response.status === 401) {
        setTeacher(null);
        await fetchActivities();
      }
      showMessage(response.ok ? result.message : result.detail, response.ok ? "success" : "error");
      if (response.ok) {
        if (method === "POST") signupForm.reset();
        await fetchActivities();
      }
    } catch (error) {
      showMessage("Unable to update registration. Please try again.", "error");
      console.error("Error updating registration:", error);
    }
  }

  accountButton.addEventListener("click", () => {
    const expanded = accountMenu.classList.toggle("hidden") === false;
    accountButton.setAttribute("aria-expanded", String(expanded));
  });
  document.getElementById("login-button").addEventListener("click", () => {
    loginError.classList.add("hidden");
    loginDialog.showModal();
  });
  document.getElementById("cancel-login").addEventListener("click", () => loginDialog.close());
  loginDialog.addEventListener("close", () => loginForm.reset());

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: document.getElementById("username").value,
          password: document.getElementById("password").value,
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        loginError.textContent = result.detail;
        loginError.classList.remove("hidden");
        return;
      }
      setTeacher(result.username);
      loginDialog.close();
      await fetchActivities();
    } catch (error) {
      loginError.textContent = "Unable to log in. Please try again.";
      loginError.classList.remove("hidden");
      console.error("Error logging in:", error);
    }
  });

  document.getElementById("logout-button").addEventListener("click", async () => {
    try {
      const response = await fetch("/auth/logout", { method: "POST" });
      if (!response.ok && response.status !== 401) throw new Error(`HTTP ${response.status}`);
      setTeacher(null);
      await fetchActivities();
      showMessage("Logged out.", "success");
    } catch (error) {
      showMessage("Unable to log out. Please try again.", "error");
      console.error("Error logging out:", error);
    }
  });

  signupForm.addEventListener("submit", (event) => {
    event.preventDefault();
    changeRegistration(activitySelect.value, document.getElementById("email").value, "POST");
  });

  async function initialize() {
    try {
      const response = await fetch("/auth/session");
      if (response.ok) {
        const session = await response.json();
        setTeacher(session.username);
      } else if (response.status !== 401) {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      showMessage("Unable to check teacher login status.", "error");
      console.error("Error checking teacher session:", error);
    }
    await fetchActivities();
  }
  initialize();
});
