let accordions = document.querySelectorAll('.accordion .toggle')

function toggleAccordion(evt) {
  let target = evt.target.dataset.accordion
  let accordion = document.querySelector(`.accordion[data-accordion="${target}"]`)
  accordion.classList.toggle("accordion-open")
}

for (let accordion of accordions) {
  accordion.addEventListener("click", toggleAccordion)
}
