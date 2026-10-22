// Retains only receivers witnessed in the primary native invocation. No events
// are invoked here; the UI driver calls the original public production methods.
export function createCase003Bindings() {
  let scope = 'runtime', presenter, manager;
  return {
    scope(value) { if (value !== undefined) scope = value; return scope; },
    capture(invocation) {
      if (scope !== 'primary_ui') return;
      if (invocation.kind === 'presenter' && invocation.method === 'confirmReset' && !presenter) {
        presenter = invocation;
      }
      if (invocation.kind === 'manager' && invocation.method === 'getResetHandle' && !manager) {
        manager = invocation;
      }
    },
    productionBindings() {
      if (!presenter || !manager || presenter.receiver.manager !== manager.receiver) {
        throw new Error('Primary UI did not bind its exact original presenter/manager');
      }
      if (presenter.receiver.confirmReset !== presenter.publicMethod ||
          manager.receiver.getResetHandle !== manager.publicMethod) {
        throw new Error('Primary production callback binding changed');
      }
      return { presenterReceiver: presenter.receiver, presenterMethod: presenter.publicMethod,
        managerReceiver: manager.receiver, managerMethod: manager.publicMethod };
    }
  };
}
