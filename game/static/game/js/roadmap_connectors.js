document.addEventListener("DOMContentLoaded", () => {
    try {
        const svg = document.getElementById("roadmap-connectors");
        const container = document.querySelector(".map-container");
        
        if (!svg || !container) return;

        function drawConnectors() {
            // Clear existing paths
            svg.innerHTML = "";

            const nodes = document.querySelectorAll(".roadmap-node");
            if (nodes.length < 2) return;

            // FIX: Force exact pixel dimensions to stop SVG scaling drift
            const containerRect = container.getBoundingClientRect();
            const width = containerRect.width;
            const height = containerRect.height;

            // Lock the SVG strictly to the exact pixel sizes
            svg.style.width = width + "px";
            svg.style.height = height + "px";
            svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

            for (let i = 0; i < nodes.length - 1; i++) {
                const node1 = nodes[i];
                const node2 = nodes[i + 1];

                const rect1 = node1.getBoundingClientRect();
                const rect2 = node2.getBoundingClientRect();

                // Calculate center points relative to the exact container top/left
                const x1 = rect1.left + (rect1.width / 2) - containerRect.left;
                const y1 = rect1.bottom - containerRect.top;

                const x2 = rect2.left + (rect2.width / 2) - containerRect.left;
                const y2 = rect2.top - containerRect.top;

                // Draw smooth S-curve
                const controlY = (y1 + y2) / 2;
                const pathData = `M ${x1} ${y1} C ${x1} ${controlY}, ${x2} ${controlY}, ${x2} ${y2}`;

                const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                path.setAttribute("d", pathData);
                path.setAttribute("stroke", "#36e6c5");
                path.setAttribute("stroke-width", "4");
                path.setAttribute("fill", "none");
                path.setAttribute("stroke-dasharray", "8, 6");
                path.setAttribute("opacity", "0.6");
                path.setAttribute("stroke-linecap", "round");

                svg.appendChild(path);
            }
        }

        // Draw immediately, then redraw after 300ms to ensure all fonts/images have fully loaded
        drawConnectors();
        setTimeout(drawConnectors, 300);

        // Instantly recalculate if the user rotates their phone or resizes the window
        let resizeTimeout;
        window.addEventListener("resize", () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(drawConnectors, 50);
        });

    } catch (error) {
        console.error("Roadmap Draw Error:", error);
    }
});