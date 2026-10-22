const need = (value, reason) => { if (!value) throw Error(reason); };
const selectors = { input:[{id:'room_address_input'},{id:'join_address_input'}],
  continue:[{id:'join_room_continue'},{id:'join_address_continue'}],cancel:[{id:'join_room_cancel'},{id:'join_address_cancel'}],
  invalid:[{id:'address_validation_message'},{id:'join_address_error'}],
  notFound:[{id:'address_notfound_label'},{id:'join_address_error'}],
  resolving:[{id:'address_loading'},{id:'join_address_loading'}] };
export async function runTask14ScalarCasesV5(spec, config, session, observer, clock, emit) {
  const result = { protocol:'task14.same-page-scalar.v5',caseId:spec.caseId,traceDigest:spec.traceDigest,
    frames:[],eventExecuted:false,failure:null,clockSnapshots:[] };
  const capture = async label => {
    const frame = await session.observeBracketed(label, selectors, () => observer.read());
    result.frames.push({label,frame,state:observer.read(),clock:clock?.read()}); return result.frames.at(-1);
  };
  const tick = async ms => { await clock.advance(ms); result.clockSnapshots.push(clock.read()); };
  try {
    need(['update_trims_and_debounces','valid_address_resolves','timeout_recovers'].includes(spec.key), 'Unknown scalar case');
    const root = await session.observeBracketed('scalar:common', {join:[{id:'join_room_by_address'}],search:[{id:'people_search_input'}]},()=>observer.read());
    need(root.controls.join.visible && root.controls.search.visible, 'Own original common UI missing');
    await session.action('click',root.controls.join.actionAncestor || root.controls.join);
    let form = await capture('setup:form');
    need(form.frame.controls.input.visible && form.state.available, 'Original form owner not acquired by real render');
    if (spec.key === 'update_trims_and_debounces') {
      need(form.state.address === '' && form.state.addressState === 'unknown', 'Empty canonical given unavailable');
      await capture('before:event');
      await session.action('input',form.frame.controls.input,spec.event.value);
      await tick(299); await capture('boundary:299');
      await tick(1); await capture('after:event');
      const first = observer.read().resolverRequests.find(r=>r.samePageResolver && !r.settled);
      need(first && clock.read().calls.some(c=>c.method==='timerCallback' && c.at===300), 'Original SDK leaf did not actually fire at300; NS');
      form = await capture('invariant:before-second-edit');
      await session.action('input',form.frame.controls.input,'#other:example.org');
      await capture('invariant:second-edit');
      observer.resolveExternal(first.id,{roomId:'!old:example.org',servers:['example.org']});
      await tick(0); await capture('invariant:stale-response');
    } else {
      await session.action('input',form.frame.controls.input,spec.given.address);
      if (spec.key === 'valid_address_resolves') {
        const before = await capture('before:event');
        need(before.state.addressState==='unknown' && before.state.address===spec.given.address,'Canonical debounce given missing');
        await tick(spec.event.elapsedMs); await capture('after:event');
        const invalid = await capture('invariant:before-invalid');
        await session.action('input',invalid.frame.controls.input,'not-a-room');
        await tick(300); await capture('invariant:invalid');
      } else {
        await tick(300);
        form = await capture('setup:pending');
        need(form.state.addressState==='resolving' && form.state.resolverRequests.some(r=>!r.settled&&r.samePageResolver), 'Own pending resolver missing');
        // Make native Loading visible through the real original Continue action.
        await session.action('click',form.frame.controls.continue);
        await capture('before:event'); await tick(spec.event.elapsedSeconds*1000); await capture('after:event');
        form = await capture('invariant:before-retry');
        await session.action('input',form.frame.controls.input,'#retry:example.org');
        await capture('invariant:retry-edit');
      }
    }
    result.eventExecuted = true;
  } catch(error) { result.failure=String(error); }
  emit({method:'Task14.scalarEpisodeV5',...result}); return result;
}
