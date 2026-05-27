const contributorsGrid = document.getElementById("contributorsGrid");

async function fetchContributors() {

  try {

    const response = await fetch(
      "https://api.github.com/repos/Checkora/Checkora/contributors"
    );

    const contributors = await response.json();

    displayContributors(contributors);

  } catch (error) {

    contributorsGrid.innerHTML = `
      <p style="text-align:center;">
        Failed to load contributors.
      </p>
    `;

    console.error(error);

  }

}

function displayContributors(contributors) {

  contributorsGrid.innerHTML = "";

  contributors.forEach((contributor) => {

    const card = document.createElement("div");

    card.className = "contributor-card";

    card.innerHTML = `
      <div class="contributor-top">

        <img
          src="${contributor.avatar_url}"
          alt="${contributor.login}"
          class="contributor-avatar"
        />

        <div class="contributor-info">

          <h3 class="contributor-name">
            ${contributor.login}
          </h3>

          <p class="contribution-count">
            ${contributor.contributions} Contributions
          </p>

        </div>

      </div>

      <a
        href="${contributor.html_url}"
        target="_blank"
        class="github-btn"
      >
        <i class="fab fa-github"></i>
        View Profile
      </a>
    `;

    contributorsGrid.appendChild(card);

  });

}

fetchContributors();