let accordions = document.getElementsByClassName('accordion')
console.log(accordions)

function toggleAccordion(evt) {
  let target = evt.target.dataset.accordion
  let content = document.querySelector(`.accordion-content[data-accordion="${target}"]`)
  console.log(evt)
  console.log(target)
  console.log(content)
  evt.target.classList.toggle("accordion-open")
  content.classList.toggle("accordion-content-open")
}

for (let accordion of accordions) {
  console.log(accordion)
  accordion.addEventListener("click", toggleAccordion)
}
