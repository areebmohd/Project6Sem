import sys
import os

print("--- ML Verification ---")
try:
    import sklearn
    print(f"Scikit-learn version: {sklearn.__version__}")
except ImportError:
    print("Scikit-learn NOT found")

try:
    import tensorflow as tf
    print(f"TensorFlow version: {tf.__version__}")
except ImportError:
    print("TensorFlow NOT found")

try:
    import scipy
    print(f"Scipy version: {scipy.__version__}")
except ImportError:
    print("Scipy NOT found")

# Try to initialize our engine
try:
    sys.path.append(os.path.join(os.getcwd(), 'backend'))
    from ml_engine import SimilarityFinder, AdvancedSentimentModel
    sf = SimilarityFinder()
    asm = AdvancedSentimentModel()
    print("ML Engine classes loaded successfully!")
    
    # Test Prediction
    test_text = "I love this new AI feature!"
    pred = asm.predict(test_text)
    print(f"Test Prediction: {pred}")
    
except Exception as e:
    print(f"Error loading ML Engine: {e}")
