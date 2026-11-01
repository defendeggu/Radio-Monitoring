import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import LanguageField from './LanguageField.svelte';

// bind:value compiles to a getter/setter pair, so this stands in for a parent component
function setup(initial = '') {
  const state = { value: initial };
  const props = {
    get value() {
      return state.value;
    },
    set value(v: string) {
      state.value = v;
    },
  };
  render(LanguageField, { props });
  return { state, select: screen.getByRole('combobox') as HTMLSelectElement };
}

describe('LanguageField', () => {
  afterEach(cleanup);

  it('defaults to automatic detection', () => {
    const { state, select } = setup();
    expect(select.value).toBe('');
    expect(state.value).toBe('');
    expect([...select.options].map((o) => o.value)).toEqual(['', 'en', 'de', 'it', 'fr', 'other']);
  });

  it('sets the ISO code of a listed language', async () => {
    const { state, select } = setup();
    await fireEvent.change(select, { target: { value: 'it' } });
    expect(state.value).toBe('it');
  });

  it('takes a free code under "other"', async () => {
    const { state, select } = setup();
    await fireEvent.change(select, { target: { value: 'other' } });
    const input = screen.getByRole('textbox');
    await fireEvent.input(input, { target: { value: 'ES' } });
    expect(state.value).toBe('es');
  });

  it('sends nothing for an invalid code and keeps the input', async () => {
    const { state, select } = setup('de');
    await fireEvent.change(select, { target: { value: 'other' } });
    const input = screen.getByRole('textbox') as HTMLInputElement;
    await fireEvent.input(input, { target: { value: 'x1' } });
    expect(state.value).toBe('');
    expect(select.value).toBe('other');
    expect(input.getAttribute('aria-invalid')).toBe('true');
  });

  it('shows an unlisted code as "other"', () => {
    const { select } = setup('rm');
    expect(select.value).toBe('other');
    expect((screen.getByRole('textbox') as HTMLInputElement).value).toBe('rm');
  });
});
