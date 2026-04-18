import argparse
import yaml
from pathlib import Path
from core.clip_orchestrator import PyPongAIClipOrchestrator

def load_config(config_path: Path) -> dict:
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("pypongai_capture", {})

def main():
    parser = argparse.ArgumentParser(description="Capture PyPongAI Gameplay Clips")
    parser.add_argument("--mode", type=str, choices=["gen_0_vs_gen_50", "progression", "test"],
                        default="test", help="Recording mode")
    parser.add_argument("--output-dir", type=str, help="Override output directory")
    parser.add_argument("--generations", type=int, default=50, help="Max generations for progression mode")
    parser.add_argument("--sample-every", type=int, default=10, help="Sampling interval for progression mode")
    
    args = parser.add_argument_group("game configuration")
    parser.add_argument("--game-path", type=str, help="Path to PyPongAI repository")
    
    args = parser.parse_args()
    
    # Load config
    # Scripts are run from content-engine root usually
    config_file = Path("config.yaml")
    base_config = load_config(config_file) if config_file.exists() else {}
    
    # Overrides
    if args.output_dir:
        base_config["output_dir"] = args.output_dir
    if args.game_path:
        base_config["game_path"] = args.game_path
        
    orchestrator = PyPongAIClipOrchestrator(base_config)
    
    print(f"Starting auto-capture in mode: {args.mode}")
    if args.mode == "test":
        result = orchestrator.record_match("test_run", duration_s=10)
        print("Test Result:", result)
    elif args.mode == "gen_0_vs_gen_50":
        results = orchestrator.record_gen_0_vs_gen_50()
        print("Hero Features Results:", results)
    elif args.mode == "progression":
        results = orchestrator.record_generation_samples(gen_start=0, gen_end=args.generations, sample_every_n=args.sample_every)
        print("Progression Results:", len(results), "clips recorded.")

if __name__ == "__main__":
    main()
