import json
from backend.execution.risk_reward_config import calculate_targets


def run_test():
    print("Running calculate_targets() smoke test...")
    res_default = calculate_targets(entry_price=100.0, signal_direction='CALL')
    res_with_max = calculate_targets(entry_price=100.0, signal_direction='CALL', max_risk_pct=0.30)

    print("DEFAULT RESULT:")
    print(json.dumps(res_default, indent=2))

    print("\nWITH max_risk_pct=0.30 RESULT:")
    print(json.dumps(res_with_max, indent=2))


if __name__ == '__main__':
    run_test()
