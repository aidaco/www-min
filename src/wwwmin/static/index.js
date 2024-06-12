for (let accordionToggle of document.querySelectorAll('.accordion .toggle')) {
  accordionToggle.addEventListener("click", function(e) {
    e.stopPropagation()
    document.querySelector(`.accordion[data-accordion="${this.dataset.accordion}"]`).classList.toggle("accordion-open")
  })
}

for (let accordion of document.querySelectorAll('.accordion')) {
  accordion.addEventListener("click", function(e) {
    if (e.target.classList.contains("accordion") || e.target.classList.contains("toggle") || e.target.classList.contains("content")) {
      document.querySelector(`.toggle[data-accordion="${this.dataset.accordion}"]`).click()
    }
  })
}

