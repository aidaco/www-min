for (let accordionToggle of document.querySelectorAll('.accordion .toggle')) {
  accordionToggle.addEventListener("click", function(e) {
    e.stopPropagation()
    document.querySelector(`.accordion[data-accordion="${this.dataset.accordion}"]`).classList.toggle("accordion-open")
  })
}

function isClickableOrChildOf(root, node) {
  if (node == root) return false;
  if (["A", "BUTTON", "INPUT", "TEXTAREA", "SELECT"].indexOf(node.tagName) > -1) return true;

  return recursive(root, node.parentNode)
}

for (let accordion of document.querySelectorAll('.accordion')) {
  accordion.addEventListener("click", function(e) {
    if (!isClickableOrChildOf(this, e.target)) {
      document.querySelector(`.toggle[data-accordion="${this.dataset.accordion}"]`).click()
    }
  })
}
