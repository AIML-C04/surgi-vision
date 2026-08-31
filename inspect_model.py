from ultralytics import YOLO

def inspect_model(model_path):
    print(f"Loading model from {model_path}...")
    model = YOLO(model_path)
    
    print("\nModel classes (model.names):")
    print(model.names)
    print(f"\nNumber of classes: {len(model.names)}")
    
if __name__ == "__main__":
    inspect_model("models/yolov8s_cholec80.pt")
