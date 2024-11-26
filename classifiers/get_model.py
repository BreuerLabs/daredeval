
from classifiers.cnn import CNN
from classifiers.mlp import MLP
# from classifiers.bitnet import BitNet
from classifiers.bido import BiDO

def get_model(config):
    if config.model.name == "CNN":
        model = CNN(config)
        
    elif config.model.name == "MLP":
        model = MLP(config)
        
    # elif config.model.name == "BitNet":
    #     model = BitNet(config)

    elif config.model.name == "BiDO":
        model = BiDO(config)

    else:
        raise ValueError(f"Unknown model: {config.model.name}")
    
    return model