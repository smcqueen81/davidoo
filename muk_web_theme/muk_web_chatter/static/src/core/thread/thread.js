/* @odoo-module */

import { patch } from "@web/core/utils/patch";

import { Thread } from '@mail/core/common/thread';

patch(Thread.prototype, {
    get displayMessages() {
        let messages = (
            this.props.order === 'asc' ?
            this.props.thread.nonEmptyMessages :
            [...this.props.thread.nonEmptyMessages].reverse()
        );
        if (!this.props.showTrackingMessages) {
            messages = messages.filter(
                (msg) => msg.trackingValues.length == 0
            );
        }
        return messages;
    },
});

Thread.props = [
    ...Thread.props,
    'showTrackingMessages',
];
