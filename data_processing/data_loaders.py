from torchvision import datasets, transforms
import torch
from torch.utils.data import random_split
from data_processing.datasets import get_datasets

def get_data_loaders(config):
    """Dynamically loads datasets based on the configuration."""
    train_dataset, val_dataset, test_dataset = get_datasets(config)

    num_workers = config.training.dataloader_num_workers
    train_loader = torch.utils.data.DataLoader(train_dataset,
                                               batch_size=config.model.hyper.batch_size,
                                               shuffle=True,
                                               num_workers=num_workers,
                                               pin_memory=True,
                                               drop_last=True,
                                               )
    val_loader = torch.utils.data.DataLoader(val_dataset,
                                             batch_size=config.model.hyper.batch_size,
                                             shuffle=False,
                                             num_workers=num_workers,
                                             pin_memory=True,
                                             drop_last=False,)
    test_loader = torch.utils.data.DataLoader(test_dataset,
                                              batch_size=config.model.hyper.batch_size,
                                              shuffle=False,
                                              num_workers=num_workers,
                                              pin_memory=True,
                                              drop_last=False,)
    
    print(f"Data loaders for {config.dataset.dataset} loaded successfully")
    
    return train_loader, val_loader, test_loader