# Fillable redesign plan

Status: user-supplied planning document, recorded verbatim on 2026-09-12 as planning task P04. It describes a gallery-style interface direction ("Tactile Document Gallery") with a design-prototype preview. Recording it accepts no implementation scope: this repository's library, workspace, editor, and localization are already implemented and verified, while the plan's scope note ("only a blank front-end template") describes the prototype project it was written for. Any future implementation here needs its own task reconciled with the existing pages and accepted decisions (including D021 Ukrainian-default localization).

## Goal

Build the selected Tactile Document Gallery as the new Fillable interface, using the real Ukrainian document-library workflow from the existing site.

## What will be built

- A responsive, collapsible left sidebar for the library, templates, documents, storage, profile, and sign-out areas.
- A clear top bar with document search and a prominent DOCX upload action.
- Template/document tabs, sorting controls, and a polished gallery using the existing document names and metadata observed on the live site.
- Working front-end interactions for search, tab switching, sorting, sidebar controls, upload selection, and document action feedback.
- Mobile and desktop layouts that preserve long Ukrainian titles without clipping or overlap.

## Visual system

- Locked palette: #F7F8FA, #172033, #2563EB, #DCE6F7.
- Sora for headings and Manrope for interface text.
- Restrained borders, compact spacing, tactile document previews, and subtle 120–180ms state transitions.
- No gradients, decorative blobs, marketing sections, or invented product areas.

## Technical details

- Replace the placeholder home screen with a React/Tailwind implementation of the selected composition.
- Add semantic design tokens and font loading through the existing global styles and document head.
- Add accessible labels, keyboard-friendly controls, responsive constraints, and reduced-motion handling.
- Add unique Fillable page metadata for search and social previews.
- Verify the final result in the live preview at desktop and mobile sizes, including interaction and overflow checks.

## Preview

- Design prototype: [Tactile Document Gallery (Lovable)](https://lovable.dev/projects/5b198c30-57f9-4f06-bac7-f6921bb5c71f).

## Scope boundary

This project currently contains only a blank front-end template, so this pass recreates the observed experience as a polished interactive design prototype. It will not connect to or alter the separate website's authentication, document storage, or server data.
