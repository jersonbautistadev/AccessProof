import { DOOR_LABEL, DOOR_MEANING, type DoorState, type Plan } from "../model";
import { DoorIcon } from "./icons";

interface Props {
  plan: Plan;
  selectedId: string | null;
  onOpen: (checkId: string, opener: HTMLElement) => void;
}

const CHANGE_LABEL = { new: "new", fixed: "fixed" } as const;

export function AccessPlan({ plan, selectedId, onOpen }: Props) {
  const present = new Set<DoorState>(
    plan.rooms.flatMap((room) => room.doors.flatMap((door) => (door ? [door.state] : []))),
  );

  return (
    <section className="plan" aria-labelledby="plan-title">
      <h2 id="plan-title" className="visually-hidden">
        Access plan
      </h2>
      <div className="plan__scroll">
        <table className="plan__table">
          <thead>
            <tr>
              <td className="plan__corner">Rooms and keycards</td>
              {plan.keycards.map((card) => {
                const check = card.identityCheck;
                const note = !check ? "no credential" : check.status === "passed" ? "verified" : "not verified";
                return (
                  <th key={card.id} scope="col" className={`keycard${check && check.status !== "passed" ? " keycard--problem" : ""}`}>
                    <span className="keycard__name">{card.id}</span>
                    <span className="keycard__note">{note}</span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {plan.rooms.map((room) => (
              <tr key={room.id}>
                <th scope="row" className={`room${room.control && room.control.status !== "passed" ? " room--problem" : ""}`}>
                  <span className="room__name">{room.id}</span>
                  <span className="room__note">
                    {room.control?.status === "passed" ? "control verified" : "control not verified"}
                  </span>
                </th>
                {room.doors.map((door, index) => {
                  const card = plan.keycards[index]?.id ?? "";
                  if (!door) {
                    return (
                      <td key={card} className="door-cell">
                        <span className="door door--empty">No check</span>
                      </td>
                    );
                  }
                  const label = `${room.id}, ${card}: ${DOOR_MEANING[door.state]}${door.change ? `, ${CHANGE_LABEL[door.change]} since baseline` : ""}. Show details`;
                  return (
                    <td key={card} className="door-cell">
                      <button
                        type="button"
                        className={`door door--${door.state}`}
                        aria-label={label}
                        aria-current={selectedId === door.check.id ? "true" : undefined}
                        onClick={(event) => onOpen(door.check.id, event.currentTarget)}
                      >
                        <DoorIcon state={door.state} />
                        <span className="door__label">{DOOR_LABEL[door.state]}</span>
                        <span className={`door__note${door.change ? " door__note--change" : ""}`}>
                          {door.change ? CHANGE_LABEL[door.change] : door.check.required ? `expected ${door.check.expected}` : "optional"}
                        </span>
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="legend" aria-label="Door states in this report">
        {[...present].map((state) => (
          <li key={state} className={`legend__item legend__item--${state}`}>
            <DoorIcon state={state} size={18} />
            {DOOR_MEANING[state]}
          </li>
        ))}
      </ul>
    </section>
  );
}
