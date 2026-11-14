from __future__ import annotations

import streamlit as st

_COMPONENT = st.components.v2.component(
    "simuru_email_multi_select",
    html="""
<div class="field">
  <label class="label" for="email-input"></label>
  <div class="control">
    <div class="chips"></div>
    <input id="email-input" type="text" autocomplete="off" />
  </div>
  <div class="options" role="listbox" hidden></div>
  <div class="help"></div>
</div>
""",
    css="""
:host {
  color: var(--st-text-color, #334155);
  font-family: var(--st-font, sans-serif);
  font-size: var(--st-base-font-size, 1rem);
}
.field { position: relative; }
.label { display: block; margin-bottom: .45rem; }
.control {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .4rem;
  min-height: 2.8rem;
  padding: .35rem .55rem;
  border: 1px solid var(--st-widget-border-color, var(--st-border-color, #e2e8f0));
  border-radius: var(--st-base-radius, .5rem);
  background: var(--st-background-color, #fff);
}
.control:focus-within {
  border-color: var(--st-primary-color, #696cff);
  box-shadow: 0 0 0 1px var(--st-primary-color, #696cff);
}
.chips { display: contents; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: .35rem;
  max-width: 100%;
  padding: .2rem .45rem;
  border-radius: 999px;
  background: color-mix(
    in srgb,
    var(--st-primary-color, #696cff) 12%,
    var(--st-secondary-background-color, #f8fafc)
  );
  color: var(--st-primary-color, #696cff);
  font-size: .88em;
}
.remove {
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  line-height: 1;
}
#email-input {
  flex: 1 1 12rem;
  min-width: 8rem;
  border: 0;
  outline: 0;
  background: transparent;
  color: inherit;
  font: inherit;
}
#email-input::placeholder {
  color: color-mix(
    in srgb,
    var(--st-text-color, #334155) 55%,
    transparent
  );
}
.options {
  position: absolute;
  z-index: 20;
  top: calc(100% + .25rem);
  right: 0;
  left: 0;
  max-height: 14rem;
  overflow: auto;
  padding: .25rem;
  border: 1px solid var(--st-border-color, #e2e8f0);
  border-radius: var(--st-base-radius, .5rem);
  background: var(--st-secondary-background-color, #fff);
  box-shadow: 0 8px 20px rgb(15 23 42 / 12%);
}
.option {
  width: 100%;
  padding: .5rem .65rem;
  border: 0;
  border-radius: calc(var(--st-base-radius, .5rem) * .65);
  background: transparent;
  color: var(--st-text-color, #334155);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.option:hover, .option[aria-selected="true"] {
  background: color-mix(
    in srgb,
    var(--st-primary-color, #696cff) 12%,
    var(--st-secondary-background-color, #f8fafc)
  );
  color: var(--st-primary-color, #696cff);
}
.help { margin-top: .35rem; color: var(--st-text-color, #334155); opacity: .7; font-size: .82em; }
""",
    js="""
export default function (component) {
  const { data, parentElement, setStateValue } = component
  const field = parentElement.querySelector(".field")
  const label = parentElement.querySelector(".label")
  const control = parentElement.querySelector(".control")
  const chips = parentElement.querySelector(".chips")
  const input = parentElement.querySelector("#email-input")
  const optionsBox = parentElement.querySelector(".options")
  const help = parentElement.querySelector(".help")
  if (!field || !label || !control || !chips || !input || !optionsBox || !help) return

  const options = Array.isArray(data?.options) ? data.options : []
  const valid = new Set(options)
  let selected = Array.isArray(data?.selected)
    ? [...new Set(data.selected.filter(value => valid.has(value)))]
    : []
  const maxSelections = Number(data?.max_selections || 0)
  label.textContent = data?.label || "Email addresses"
  input.placeholder = data?.placeholder || "Search email addresses..."
  help.textContent = data?.help || "Select a suggestion; use comma or Tab to add it."
  chips.replaceChildren()

  function publish() {
    selected = [...new Set(selected.filter(value => valid.has(value)))]
    setStateValue("selected", selected)
  }

  function remove(value) {
    selected = selected.filter(item => item !== value)
    renderChips()
    publish()
    renderOptions()
  }

  function renderChips() {
    chips.replaceChildren()
    for (const value of selected) {
      const chip = document.createElement("span")
      chip.className = "chip"
      const text = document.createElement("span")
      text.textContent = value
      const removeButton = document.createElement("button")
      removeButton.className = "remove"
      removeButton.type = "button"
      removeButton.textContent = "×"
      removeButton.setAttribute("aria-label", `Remove ${value}`)
      removeButton.onclick = () => remove(value)
      chip.append(text, removeButton)
      chips.append(chip)
    }
  }

  let matches = []
  let highlighted = 0
  function renderOptions() {
    const query = input.value.trim().toLowerCase()
    matches = options.filter(value =>
      !selected.includes(value) && (!query || value.toLowerCase().includes(query))
    )
    highlighted = Math.min(highlighted, Math.max(matches.length - 1, 0))
    optionsBox.replaceChildren()
    for (const [index, value] of matches.entries()) {
      const option = document.createElement("button")
      option.className = "option"
      option.type = "button"
      option.setAttribute("role", "option")
      option.setAttribute("aria-selected", String(index === highlighted))
      option.textContent = value
      option.onmousedown = event => event.preventDefault()
      option.onclick = () => add(value)
      optionsBox.append(option)
    }
    optionsBox.hidden = matches.length === 0
  }

  function add(value) {
    if (!valid.has(value) || selected.includes(value)) {
      input.value = ""
      renderOptions()
      return
    }
    if (maxSelections && selected.length >= maxSelections) return
    selected.push(value)
    input.value = ""
    renderChips()
    publish()
    renderOptions()
    input.focus()
  }

  function addExact(token) {
    const normalized = token.trim().toLowerCase()
    const match = options.find(value => value.toLowerCase() === normalized)
    if (match) add(match)
    else renderOptions()
  }

  input.oninput = () => {
    const comma = input.value.lastIndexOf(",")
    if (comma >= 0) {
      const token = input.value.slice(0, comma)
      const normalized = token.trim().toLowerCase()
      const match = options.find(value => value.toLowerCase() === normalized)
      if (match && (!maxSelections || selected.length < maxSelections)) {
        selected.push(match)
        input.value = ""
        renderChips()
        publish()
      }
    }
    renderOptions()
  }
  input.onkeydown = event => {
    if (event.key === "ArrowDown" && matches.length) {
      event.preventDefault()
      highlighted = (highlighted + 1) % matches.length
      renderOptions()
    } else if (event.key === "ArrowUp" && matches.length) {
      event.preventDefault()
      highlighted = (highlighted - 1 + matches.length) % matches.length
      renderOptions()
    } else if (event.key === "Enter" && matches.length && input.value.trim()) {
      event.preventDefault()
      add(matches[highlighted])
    } else if (event.key === "Tab" && matches.length && input.value.trim()) {
      event.preventDefault()
      add(matches[highlighted])
    } else if (event.key === "," && input.value.trim()) {
      event.preventDefault()
      addExact(input.value)
    } else if (event.key === "Backspace" && !input.value && selected.length) {
      remove(selected[selected.length - 1])
    } else if (event.key === "Escape") {
      optionsBox.hidden = true
    }
  }
  input.onfocus = renderOptions
  input.onblur = () => {
    window.setTimeout(() => { optionsBox.hidden = true }, 120)
  }
  renderChips()
  renderOptions()
  return () => {
    input.oninput = null
    input.onkeydown = null
    input.onfocus = null
    input.onblur = null
  }
}
""",
)


def email_multi_select(
    label: str,
    options: list[str],
    *,
    key: str,
    placeholder: str = "Search email addresses...",
    help_text: str = "Select a suggestion; use comma or Tab to add it.",
    max_selections: int | None = None,
) -> list[str]:
    valid_options = list(dict.fromkeys(options))
    state = st.session_state.get(key, {})
    if isinstance(state, dict):
        state_selected = state.get("selected", [])
    else:
        state_selected = [state] if isinstance(state, str) else []
    selected = _valid_selection(state_selected, valid_options)
    if isinstance(state, str):
        st.session_state.pop(key, None)
    result = _COMPONENT(
        key=key,
        data={
            "label": label,
            "options": valid_options,
            "selected": selected,
            "placeholder": placeholder,
            "help": help_text,
            "max_selections": max_selections or 0,
        },
        default={"selected": selected},
        on_selected_change=lambda: None,
    )
    return _valid_selection(result.selected, valid_options)


def _valid_selection(value: object, options: list[str]) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    allowed = set(options)
    return list(dict.fromkeys(item for item in value if isinstance(item, str) and item in allowed))
