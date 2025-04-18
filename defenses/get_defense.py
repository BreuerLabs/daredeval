from defenses.label_smoothing import apply_label_smoothing_defense
from defenses.bido import apply_bido_defense
from defenses.mid import apply_MID_defense
from defenses.tldmi import apply_TLDMI_defense
from defenses.gaussian_noise import apply_gaussian_noise_defense
from defenses.rolss import apply_RoLSS_defense
from defenses.sparse import apply_sparse_defense

def get_defense(config, model):
    
    defense_name = config.defense.name
    
    if defense_name == "label_smoothing":
        model = apply_label_smoothing_defense(config, model)
        
    elif defense_name == "MID":
        model = apply_MID_defense(config, model)

    elif defense_name == "bido":
        model = apply_bido_defense(config, model)

    elif defense_name == "tldmi":
        model = apply_TLDMI_defense(config, model)

    elif defense_name == "gaussian_noise":
        model = apply_gaussian_noise_defense(config, model)

    elif defense_name == "rolss":
        model = apply_RoLSS_defense(config, model)

    elif defense_name == "sparse":
        model = apply_sparse_defense(config, model)

    elif defense_name == "no_defense":
        pass # model stays as is
        
    else:
        raise ValueError(f"Unknown defense: {defense_name}")
    
    return model