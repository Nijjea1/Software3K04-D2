"""Interactive demonstration front end.

Run with:  python3 -m adc.main

This file is deliberately thin. It only reads commands and calls the App's
exported operations, so the TAs can see that no behaviour lives here.
"""
from adc.app import AdcApplication
from adc.behaviour.authorization import Role
from adc.hardware.clock import SimulatedClock
from adc.hardware.credential_reader import SimulatedCredentialReader
from adc.hardware.drawer_sensor import SimulatedDrawerSensor
from adc.hardware.lock_driver import SimulatedLockDriver
from adc.hardware.removal_sensor import SimulatedRemovalSensor

DRAWERS = ["D1", "D2", "D3"]
ITEMS = [
    # item_id, drawer, starting quantity, max capacity
    ("MORPH-10MG", "D1", 12, 40),
    ("PARA-500MG", "D2", 30, 60),
    ("INSUL-100U", "D3", 8, 20),
]
TOKENS = {"card-nurse": "u-nurse-01", "card-pharm": "u-pharm-01",
          "card-tech": "u-tech-01", "card-rev": "u-rev-01",
          "card-old": "u-nurse-99"}
ROLES = {"u-nurse-01": Role.NURSE, "u-pharm-01": Role.PHARMACIST,
         "u-tech-01": Role.TECHNICIAN, "u-rev-01": Role.SAFETY_REVIEWER,
         "u-nurse-99": Role.NURSE}
INACTIVE = {"u-nurse-99"}

HELP = """
Commands
  status                      mode, link, drawer and stock summary
  login <token>               card-nurse | card-pharm | card-tech | card-rev | card-old
  logout
  dispense <item> <qty>       e.g. dispense MORPH-10MG 2
  confirm                     confirm the screen and unlock one drawer
  take                        simulate the item being physically removed
  close                       close the drawer and resolve the transaction
  replenish <item> <drawer> <qty>
  poll                        run the 10 second hardware health check
  openfault                   leave the drawer open, then poll, FR-FLT-01
  lockfault <drawer>          jam the lock feedback, then poll, FR-FLT-02
  clearfault                  technician or pharmacist reset, FR-MOD-04
  maint / exitmaint           enter and leave MAINTENANCE
  advance <seconds>           move the simulated clock forward
  linkdown                    advance past the heartbeat timeout, then poll
  linkup                      restore the link and begin RESYNC
  queue                       show stored outbound messages, oldest first
  ack <MSG-xxxxx>             simulate Part B acknowledging a message
  badmsg                      send a malformed inbound message, NFR-SEC-04
  audit [n]                   last n audit records
  help / quit
"""


# Builds one cabinet with the simulated hardware and the demo stock and staff.
# All the wiring in one place. Swapping a Simulated class for a real driver is
# a change to these five lines and nothing else.
def build():
    clock = SimulatedClock()
    lock = SimulatedLockDriver(DRAWERS)
    drawers = SimulatedDrawerSensor(DRAWERS)
    reader = SimulatedCredentialReader(TOKENS)
    removal = SimulatedRemovalSensor()
    app = AdcApplication("ADC-WARD-3B", clock, lock, drawers, reader, removal,
                         DRAWERS, ITEMS, ROLES, INACTIVE)
    return app, clock, lock, drawers, removal


# Prints the status banner, every drawer, and the current stock.
def show_status(app):
    print(app.banner())
    print("  drawers:")
    for d, state, lk in app.drawer_report():
        print("    %-4s %-11s %s" % (d, state, lk))
    print("  stock:")
    for item, (drawer, qty, rev) in sorted(app.inventory_snapshot().items()):
        print("    %-12s drawer %-3s qty %-4d rev %d" % (item, drawer, qty, rev))


# The command loop. Reads a word, calls one App method, prints what came back.
# The loop below only parses words and calls App methods. No rule, threshold or
# decision lives in this file, which is the point of keeping it thin.
def main():
    app, clock, lock, drawers, removal = build()
    print("ADC Part A, Deliverable 2 demonstration")
    print("Mode after startup:", app.start_up().value)
    print(HELP)
    while True:
        try:
            raw = input("adc> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not raw:
            continue
        parts = raw.split()
        cmd, args = parts[0].lower(), parts[1:]
        try:
            if cmd in ("quit", "exit"):
                return
            elif cmd == "help":
                print(HELP)
            elif cmd == "status":
                show_status(app)
            elif cmd == "login":
                _, msg = app.authenticate(args[0])
                print(msg)
            elif cmd == "logout":
                print(app.log_out())
            elif cmd == "dispense":
                tx, msg = app.request_dispense(args[0], int(args[1]))
                print(msg)
            elif cmd == "confirm":
                # Each transaction starts with removal unconfirmed. The sensor
                # reports per transaction, so a previous "take" must not carry
                # over and silently confirm the next dispense.
                for d in DRAWERS:
                    removal.set_confirmed(d, False)
                print(app.confirm_dispense())
            elif cmd == "take":
                for d in DRAWERS:
                    removal.set_confirmed(d, True)
                print("Removal sensor now reports confirmed.")
            elif cmd == "close":
                for d in DRAWERS:
                    drawers.set_closed(d)
                print(app.close_drawer_and_complete())
            elif cmd == "replenish":
                print(app.replenish(args[0], args[1], int(args[2])))
            elif cmd == "poll":
                print(app.poll_hardware())
            elif cmd == "openfault":
                for d in DRAWERS:
                    drawers.set_open(d)
                clock.advance(11)
                print("Drawer left open and 11 s elapsed.")
                print(app.poll_hardware())
            elif cmd == "lockfault":
                lock.inject_feedback_fault(args[0])
                print("Lock feedback on %s is jammed." % args[0])
                print("  poll at t+0s:", app.poll_hardware())
                clock.advance(3)
                print("  poll at t+3s:", app.poll_hardware())
            elif cmd == "clearfault":
                lock.clear_feedback_fault("D1")
                lock.clear_feedback_fault("D2")
                lock.clear_feedback_fault("D3")
                for d in DRAWERS:
                    drawers.set_closed(d)
                print(app.clear_fault(self_test_passes=True))
            elif cmd == "maint":
                print(app.enter_maintenance())
            elif cmd == "exitmaint":
                print(app.exit_maintenance())
            elif cmd == "advance":
                clock.advance(float(args[0]))
                print("Clock is now %.1f s." % clock.now_s())
            elif cmd == "linkdown":
                clock.advance(16)
                print(app.poll_hardware())
            elif cmd == "linkup":
                print(app.simulate_link_restored())
                for line in app.flush_queue():
                    print(" ", line)
            elif cmd == "queue":
                rows = app.pending_messages()
                if not rows:
                    print("Queue empty.")
                for seq, msg_id, kind in rows:
                    print("  %3d  %-10s %s" % (seq, msg_id, kind))
            elif cmd == "ack":
                print(app.monitor_response(
                    '{"v":1,"id":"IN-1","kind":"ACK","payload":{"ack_id":"%s"}}' % args[0]))
            elif cmd == "badmsg":
                print(app.monitor_response('{"v":9,"id":"IN-X","kind":"ACK"}'))
            elif cmd == "audit":
                n = int(args[0]) if args else 12
                for r in app.audit_tail(n):
                    print("  #%-4d t=%-8.1f %-13s %-10s %-11s %s"
                          % (r["seq"], r["timestamp_s"], r["event_type"],
                             r["outcome"], r["user_id"] or "-", r["detail"]))
            else:
                print("Unknown command. Type help.")
        except AssertionError as exc:
            print("INVARIANT VIOLATION:", exc)
        except IndexError:
            print("Missing argument. Type help.")
        except ValueError as exc:
            print("Bad argument:", exc)


if __name__ == "__main__":
    main()
