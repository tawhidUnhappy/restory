/**
 * restory.virtual_scroll — Viewport windowing renderer for ultra-tall webtoon canvas strips.
 */

class VirtualStripScroll {
    constructor(containerEl, pages, totalHeight) {
        this.container = containerEl;
        this.pages = pages;
        this.totalHeight = totalHeight;
        this.visibleBuffer = 2000;
    }

    renderViewport(scrollTop, viewportHeight) {
        let minY = scrollTop - this.visibleBuffer;
        let maxY = scrollTop + viewportHeight + this.visibleBuffer;

        let currY = 0;
        this.pages.forEach((page) => {
            let pageH = page.height || 1200;
            let pageTop = currY;
            let pageBottom = currY + pageH;

            let imgEl = document.getElementById(`img-${page.stem}`);
            if (pageBottom >= minY && pageTop <= maxY) {
                if (!imgEl) {
                    imgEl = document.createElement("img");
                    imgEl.id = `img-${page.stem}`;
                    imgEl.src = `/image/download/${page.chapter}/${page.filename}`;
                    imgEl.style.position = "absolute";
                    imgEl.style.top = `${pageTop}px`;
                    imgEl.style.left = "0px";
                    imgEl.style.width = "100%";
                    this.container.appendChild(imgEl);
                }
            } else {
                if (imgEl) imgEl.remove();
            }

            currY += pageH;
        });
    }
}