/* restory — Virtual Scroll Container Helper */

class VirtualStripContainer {
    constructor(containerEl, pagesList, chapter) {
        this.container = containerEl;
        this.pages = pagesList;
        this.chapter = chapter;
        this.renderedImages = [];
    }

    renderAllPages() {
        this.container.innerHTML = '';
        let currentTop = 0;

        this.pages.forEach((page, idx) => {
            const img = document.createElement('img');
            img.dataset.filename = page.filename;
            img.style.display = 'block';
            img.style.width = '100%';
            img.src = `/image/download/${this.chapter}/${page.filename}`;
            
            this.container.appendChild(img);
            this.renderedImages.push(img);
        });
    }
}