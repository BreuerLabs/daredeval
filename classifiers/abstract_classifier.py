import torch
import torch.nn as nn
import numpy as np
import wandb
from tqdm import tqdm
import omegaconf
from omegaconf import OmegaConf

# from classifiers.defense_utils import ElementwiseLinear
# from utils.plotting import plot_tensor


class AbstractClassifier(nn.Module):
    """ 
    This is an abstract class for the classifiers. It contains the train, forward, predict, save_model, load_model methods. It should not be used directly. 
    """
    
    def __init__(self, config):
        super(AbstractClassifier, self).__init__()
        self.device = config.training.device
        self.config = config

        if config.model.criterion == "crossentropy":
            self.criterion = nn.CrossEntropyLoss()
            self.criterionSum = nn.CrossEntropyLoss(reduction='sum')

        if config.model.criterion == "MSE":
            self.criterion = nn.MSELoss()
            self.criterionSum = nn.MSELoss(reduction='sum')

        # ## Defenses
        # if config.defense.name == "drop_layer":
        #     self.input_defense_layer = self.init_input_defense_layer()
        #     if self.config.defense.penalty == "skip_lasso":
        #         self.skip_defense_layer = self.init_skip_defense_layer()
        # else:
        #     self.input_defense_layer = None
        
        if config.defense.name == "struppek":
            self.criterion.label_smoothing = config.defense.alpha
            self.criterionSum.label_smoothing = config.defense.alpha        

    def init_model(self):
        model = None
        return model

    # def init_input_defense_layer(self):

    #     if self.config.model.flatten:
    #         in_features = (self.config.dataset.input_size[1] * self.config.dataset.input_size[2] * self.config.dataset.input_size[0],)
    #     else:
    #         in_features = (self.config.dataset.input_size[0], self.config.dataset.input_size[1], self.config.dataset.input_size[2])

    #     defense_layer = ElementwiseLinear(in_features, w_init=self.config.defense.input_defense_init)

    #     return defense_layer

    # def init_skip_defense_layer(self):
    #     pass
    #     # skip = nn.Linear(in_features, self.config.dataset.n_classes, bias=False)
    
    def train_one_epoch(self, train_loader):
        
        self.train()
        total_loss = 0
        loss_calculated = 0
        for batch_idx, (data, target) in enumerate(train_loader):
            data, target = data.to(self.device), target.to(self.device)
            self.optimizer.zero_grad()
            output = self(data)

            loss = self.get_loss(output, target)

            total_loss += loss.item()          

            loss_calculated += len(data)

            if self.config.training.verbose == 2:
                print("loss: ", loss.item())

            loss.backward()
            self.optimizer.step()
            self.train_step += 1

            # AbstractClassifiers overwrite this method with anything that needs to be done before the next batch is read
            self.post_batch()
            
            # if self.config.defense.name == "drop_layer" and self.config.defense.apply_threshold:
            #    self.apply_threshold()

            # track_features = self.config.training.wandb.track_features
            # if track_features:
            #     if isinstance(track_features, omegaconf.listconfig.ListConfig):
            #         feature_norms = self.get_feature_norms()
            #         for idx, feature_norm in zip(track_features, feature_norms):
            #             wandb.log({f"feature_{idx}" : feature_norm.item(), "train_step": self.train_step})
            #     wandb.log({"n_features" : self.n_features_remaining, "train_step" : self.train_step})


        train_loss = total_loss / loss_calculated

        return train_loss

    def post_batch(self):
        pass
    
    def train_model(self, train_loader, val_loader):

        if self.config.training.save_as:
            self.save_as = self.config.training.save_as + ".pth"
        elif self.config.training.wandb.track:
            self.save_as = wandb.run.name + ".pth" 
        else:
            raise ValueError("Please provide a name to save the model when not using wandb tracking")
        
        if self.config.model.optimizer == "adam":
            self.optimizer = torch.optim.Adam(self.parameters(),
                                              lr=self.config.model.hyper.lr,
                                              betas=(0.9, self.config.model.hyper.beta2),
                                              )

        if self.config.model.lr_scheduler == "MultiStepLR": 
            self.lr_scheduler = torch.optim.lr_scheduler.MultiStepLR(self.optimizer,
                                                             milestones=self.config.model.hyper.milestones,
                                                             gamma=self.config.model.hyper.gamma,
                                                             )

        self.train_step = 0

        self.to(self.device)
        
        best_loss = np.inf
        no_improve_epochs = 0

        print("\nTraining using ", self.device)
        
        for epoch in tqdm(range(self.config.model.hyper.epochs), desc="Training", total=self.config.model.hyper.epochs):         
            train_loss = self.train_one_epoch(train_loader)

            if self.config.training.verbose:
                print(f'Epoch: {epoch + 1}') 
                print(f"Train loss: {train_loss}")
            
            if self.config.training.wandb.track:
                wandb.log({"train_loss": train_loss, "train_step": self.train_step, "epoch": epoch+1})
                if self.config.model.lr_scheduler:
                    wandb.log({"learning_rate" : self.lr_scheduler.get_last_lr()[0], "train_step" : self.train_step, "epoch": epoch+1})

            if val_loader and epoch % self.config.training.evaluate_freq == 0:
                val_loss, val_accuracy = self.evaluate(val_loader)

                _, train_accuracy = self.evaluate(train_loader)
                
                if self.config.training.verbose:
                    print(f'Train Accuracy: {train_accuracy}')
                    print(f'Validation loss: {val_loss}') 
                    print(f'Val Accuracy: {val_accuracy}')
                
                if self.config.training.wandb.track:
                    wandb.log({"train_accuracy": train_accuracy, "train_step": self.train_step, "epoch": epoch+1})
                    wandb.log({"val_loss": val_loss, "train_step": self.train_step, "epoch": epoch+1})
                    wandb.log({"val_accuracy": val_accuracy, "train_step": self.train_step, "epoch": epoch+1})
                
                if val_loss < best_loss:
                    best_loss = val_loss
                    self.save_model(self.save_as)
                    no_improve_epochs = 0

                else:
                    no_improve_epochs += 1
                    if no_improve_epochs >= self.config.model.hyper.patience:
                        print("Early stopping")
                        break

            if self.config.model.lr_scheduler:
                self.lr_scheduler.step()

            self.post_epoch(epoch)

            # if epoch % self.config.training.save_defense_layer_freq == 0:
            #     # save defense layer mask plot
            #     if self.config.defense.name == "drop_layer" and self.config.defense.plot_mask:
            #         w_first = self.input_defense_layer.weight.data
                    
            #         n_channels, x_dim, y_dim = self.config.dataset.input_size
            #         if n_channels == 3:
            #             w_norms = torch.linalg.norm(w_first, dim=0)
            #         else: # n_channels == 1
            #             w_norms = w_first.abs() # does the same thing as norm of dim=0 when n_channels is 1, but this is more readable
                        
            #         w_norms = w_norms.reshape((1, x_dim, y_dim))

            #         plt = plot_tensor(w_norms.cpu(), self.save_as)
            #         if self.config.training.wandb.track:
            #             wandb.log({"defense_mask" : plt, "train_step": self.train_step, "epoch": epoch+1})


                


        # save train loss and accuracy
        final_train_loss, final_train_accuracy = self.evaluate(train_loader)
        if self.config.training.verbose:
            print(f'Final train loss: {final_train_loss}') 
            print(f'Final train accuracy: {final_train_accuracy}')
        
        if self.config.training.wandb.track:
            wandb.log({"final_train_loss": final_train_loss, "train_step": self.train_step, "epoch": epoch+1})
            wandb.log({"final_train_accuracy": final_train_accuracy, "train_step": self.train_step, "epoch": epoch+1})
                 
        # Load the best model
        self.load_model(f"classifiers/saved_models/{self.save_as}", map_location=self.device)
    
    def post_epoch(self, epoch):
        pass

    
    def evaluate(self, loader):
        self.to(self.device)
        self.eval()
        
        correct = 0
        total_loss = 0
        total_instances = 0
        
        with torch.no_grad():
            for batch_idx, (data, target) in enumerate(loader):
                data, target = data.to(self.device), target.to(self.device)
                output = self(data)

                loss = self.get_loss(output, target)

                total_loss += loss.item()
                total_instances += len(data)
                
                pred = torch.argmax(output, dim=1)
                correct += (pred == target).sum().item()
        
        avg_loss = total_loss / total_instances
        accuracy = correct / total_instances
        
        return avg_loss, accuracy

    def get_loss(self, output, target): # calculate loss with whatever penalties added 
        
        loss = self.criterionSum(output, target)
        
        # if self.config.defense.name == "drop_layer": # normal lasso on first layer weights
        #     lasso_pen = self.config.defense.lasso.lambda_ * self.lasso_penalty()
        #     loss = loss + lasso_pen
                
        return loss

    def forward(self, x):
        if self.config.model.flatten:
            batch_size = x.shape[0]
            x = torch.reshape(x, (batch_size, -1))

        # if self.input_defense_layer is not None:
        #     x = self.input_defense_layer(x)

        return self.model(x)

    def predict(self, X):
        return torch.argmax(self.forward(X), dim=1)
    
    def save_model(self, name):
        path = f"classifiers/saved_models/{name}"
        torch.save(self.state_dict(), path)

        
    def load_model(self, file_path, map_location = None):
        if map_location is None:
            state_dict = torch.load(file_path, weights_only=True)
            self.load_state_dict(state_dict)
            
        else:
            state_dict = torch.load(file_path, map_location=map_location, weights_only=True)

            self.load_state_dict(state_dict)

    # def apply_threshold(self):
    #     if self.config.defense.name == "drop_layer":
    #         thresh = self.config.defense.lasso.threshold
    #         current_w_first = self.input_defense_layer.weight.data # (n_channels, x_dim, y_dim)
    #         current_w_norms = torch.linalg.norm(current_w_first, dim=0) # (x_dim, y_dim)
    #         below_threshold = current_w_norms <= thresh  # (x_dim, y_dim)
    #         new_w_first = current_w_first * ~below_threshold # (n_channels, x_dim, y_dim) x (x_dim, y_dim) = (n_channels, x_dim, y_dim)
    #         self.input_defense_layer.weight.data = new_w_first
    #         self.n_features_remaining = below_threshold.numel() - below_threshold.sum()
    #     else:
    #         assert 0 == 1, f"apply_threshold not yet implemented for defense {self.config.defense.name}"

    # def lasso_penalty(self): # Lasso penalty on one-dimensional weights
        
    #     w_first = self.input_defense_layer.weight
    #     w_norms = torch.linalg.norm(w_first, dim=0) # takes L2 norm over n_channels. Performs abs() when n_channels=1, combines RGB values of pixels (group lasso) when n_channels=3
        
    #     if self.config.defense.lasso.smooth:
    #         alpha = self.config.defense.lasso.alpha
    #         smoothed_norms = (w_norms**2 / (2*alpha)) + (alpha/2) # see eqn. (15) in SGLasso paper
    #         final_smoothed_norms = torch.zeros_like(w_norms)
    #         final_smoothed_norms[w_norms < alpha] = smoothed_norms[w_norms < alpha]
    #         final_smoothed_norms[w_norms >= alpha] = w_norms[w_norms >= alpha] # only use smoothed norms if less than alpha
    #         lasso_pen = final_smoothed_norms.sum()
    #     else:
    #         lasso_pen = w_norms.sum()

    #     return lasso_pen
    



