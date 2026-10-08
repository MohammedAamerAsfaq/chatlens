<script setup>
import ProductPriceUpdateView from '@/views/ProductPriceUpdateView.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader
      eyebrow="Workflow control"
      title="Automation"
      description="Configure and monitor company-owned automations from one workspace."
    />

    <nav class="automation-navigation" aria-label="Automation sections">
      <a class="automation-navigation__item active" href="#price-automation">
        <span class="automation-navigation__icon" aria-hidden="true">$</span>
        <span>
          <strong>Price Automation</strong>
          <small>Inventory quantity, cost, and sale price rules</small>
        </span>
      </a>
    </nav>

    <section id="price-automation" class="automation-panel">
      <header class="automation-panel__header">
        <div>
          <p class="ui-eyebrow">Prices</p>
          <h2>Price Automation</h2>
          <p>Watch selected WhatsApp contacts and groups, process matched price lists, and review every detection.</p>
        </div>
      </header>
      <ProductPriceUpdateView mode="automation" />
    </section>
  </UiPage>
</template>

<style scoped>
.automation-navigation {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 360px));
  gap: 14px;
  margin-bottom: 22px;
}
.automation-navigation__item {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 16px;
  color: var(--ui-text);
  text-decoration: none;
  background: var(--ui-surface);
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius-lg);
  box-shadow: var(--ui-shadow-card);
}
.automation-navigation__item.active { border-color: var(--ui-primary); }
.automation-navigation__icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  flex: 0 0 auto;
  color: #fff;
  font-size: 20px;
  font-weight: 800;
  background: var(--ui-primary);
  border-radius: 12px;
}
.automation-navigation__item span:last-child { display: grid; gap: 3px; }
.automation-navigation__item strong { font-size: 15px; }
.automation-navigation__item small { color: var(--ui-text-muted); }
.automation-panel {
  padding: 24px;
  background: var(--ui-surface);
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius-lg);
  box-shadow: var(--ui-shadow-card);
  scroll-margin-top: 20px;
}
.automation-panel__header {
  padding-bottom: 20px;
  margin-bottom: 22px;
  border-bottom: 1px solid var(--ui-border);
}
.automation-panel__header h2 { margin: 4px 0 6px; color: var(--ui-text); font-size: 24px; }
.automation-panel__header p:last-child { margin: 0; color: var(--ui-text-muted); }
@media (max-width: 720px) {
  .automation-panel { padding: 16px; }
}
</style>
