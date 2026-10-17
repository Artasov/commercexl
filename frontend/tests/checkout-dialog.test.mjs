import assert from "node:assert/strict";
import test from "node:test";
import {CommerceCheckoutDialog} from "../packages/ui/dist/CommerceCheckoutDialog.js";

test("close icon and overlay/keyboard dismissal respect the pending payment lock", () => {
  for (const closeDisabled of [false, true]) {
    const changes = [];
    const root = CommerceCheckoutDialog({open:true, title:"Payment", closeLabel:"Close", children:"Payment details", closeDisabled, onOpenChange:value => changes.push(value)});
    const content = root.props.children;
    const header = content.props.children[0];
    const close = header.props.children[1];
    assert.equal(close.props.disabled, closeDisabled);
    close.props.onClick();
    root.props.onOpenChange(false);
    assert.deepEqual(changes, closeDisabled ? [] : [false, false]);
    assert.equal(header.props.children[0].props.children, "Payment");
    assert.equal(close.props.children[1].props.children, "Close");
    assert.equal(content.props.children.length, 3);
  }
});
