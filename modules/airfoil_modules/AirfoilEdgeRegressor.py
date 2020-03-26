from ..utils.OnlineTorchLearner import OnlineTorchLearner

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils import data
from torchvision import transforms

from pprint import pprint

import json, os, os.path, pickle

from time import sleep
from PIL import Image

class EdgeRegressorModel(nn.Module):
    def __init__(self, depth=1, activation=nn.ReLU, out_size=60, mid_channels=8):
        nn.Module.__init__(self)
        self.norm = nn.BatchNorm2d(4)
        self.conv_layers = []
        for i in range(depth):
            if i == 0:
                channels = 4
            else:
                channels = 8
            self.conv_layers.append(nn.Sequential(
                nn.Conv2d(channels, mid_channels, 3, padding=1),
                nn.Conv2d(mid_channels, mid_channels, 3, padding=1),
                nn.BatchNorm2d(mid_channels),
                activation()
                ))
            if i < 4 and i > 1:
                self.conv_layers.append(nn.MaxPool2d(2))
        self.prefinal = nn.Sequential(
            nn.Linear(56 * 56 * mid_channels, 1000),
            )
        self.final = nn.Sequential(nn.Linear(1000, out_size))

    def forward(self, x):
        x = self.norm(x)
        for layer in self.conv_layers:
            x = layer(x)
        x = x.view(-1, 56 * 56 * 8)
        x = self.prefinal(x)
        x = self.final(x)
        x = x.double()
        print('Output:')
        print(x.size())
        return x

class AirfoilEdgeRegressor(OnlineTorchLearner):
    def __init__(self, filename='data/models/airfoil_edge_regressor.nn', name='AirfoilEdgeRegressor'):
        self.driver = None
        OnlineTorchLearner.__init__(self, nn.MSELoss, optim.Adadelta, dict(lr=1.0, rho=0.9, eps=1e-06, weight_decay=0), in_label='AugmentedAirfoilPlot', name=name, filename=filename)

    def load_image(self, filename):
        tfms = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor()])
        image = Image.open(filename)
        image.putalpha(255)
        img = tfms(image)
        img = img.unsqueeze(0)
        return img

    def load_labels(self, parent):
        parent = self.driver.get(parent)
        with open(parent['coord_file'], 'rb') as infile:
            coordinates = pickle.load(infile)
        fx, fy, sx, sy, camber = coordinates
        fx = [x for i, x in enumerate(fx) if i % 10 == 0]
        fy = [y for i, y in enumerate(fy) if i % 10 == 0]
        sy = [y for i, y in enumerate(sy) if i % 10 == 0]
        coordinates = sum(map(list, [fx, fy, sy]), [])
        labels = torch.tensor(coordinates, dtype=torch.double)
        return labels.unsqueeze(0)

    def init_model(self):
        self.model = EdgeRegressorModel(depth=6)

    def transform(self, node):
        try:
            labels = self.load_labels(node.data['parent'])
            image  = self.load_image(filename = node.data['filename'])
            yield image, labels
        except ValueError as e:
            print(e)
            pass

    def process(self, node, driver=None):
        1/0

    def learn(self, items):
        input_list = []
        label_list = []
        for node in items:
            for inputs, labels in self.transform(node):
                input_list.append(inputs)
                label_list.append(labels)
        self.optimizer.zero_grad()
        inputs = torch.cat(input_list)
        labels = torch.cat(label_list)
        outputs = self.model(inputs)
        print('Labels:')
        print(labels.size())
        loss = self.criterion(outputs, labels)
        loss.backward()
        self.optimizer.step()
        print('{} loss: '.format(self.name), loss.item(), flush=True)

    def process_batch(self, batch, driver=None):
        print('Batch:', len(batch.items), flush=True)
        if self.driver is None:
            self.driver = driver[0](driver[1])
        if os.path.isfile(self.filename):
            self.load()
        self.learn(batch.items)
        self.save()
        return []

