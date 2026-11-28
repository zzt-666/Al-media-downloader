/** Smooth-scroll so the target sits just under the sticky header. */
export function scrollToId(id) {
  const el = document.getElementById(id)
  if (!el) return

  const header = document.querySelector('header.sticky')
  const headerH = header ? header.getBoundingClientRect().height : 64
  const gap = 12
  const top = el.getBoundingClientRect().top + window.scrollY - headerH - gap

  window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  if (typeof history !== 'undefined') {
    history.replaceState(null, '', `#${id}`)
  }
}
