# Kaiyu Li
# https://github.com/likyoo

import torch.nn as nn
import torch

class CA_Layer(nn.Module):
    def __init__(self, channel, reduction=16):
        super(CA_Layer, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)

        self.conv_du = nn.Sequential(
            nn.Conv2d(channel, channel // reduction,
                      kernel_size=1, padding=0, bias=True),
            nn.ReLU(inplace=True),
            nn.Conv2d(channel // reduction, channel,
                      kernel_size=1, padding=0, bias=True),
            nn.Sigmoid()
        )

    def forward(self, x):
        y = self.avg_pool(x)
        y = self.conv_du(y)
        return x * y


class Conv_Block_Nested(nn.Module):
    def __init__(self, in_ch, mid_ch, out_ch):
        super(Conv_Block_Nested, self).__init__()
        self.activation = nn.ReLU(inplace=True)
        self.conv1 = nn.Conv2d(in_ch, mid_ch, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(mid_ch)
        self.conv2 = nn.Conv2d(mid_ch, out_ch, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(out_ch)
        self.ca = CA_Layer(out_ch)

    def forward(self, x):
        x = self.conv1(x)
        identity = x
        x = self.bn1(x)
        x = self.activation(x)

        x = self.conv2(x)
        x = self.bn2(x)
        x = self.ca(x)
        output = self.activation(x + identity)
        return output


class up(nn.Module):
    def __init__(self, in_ch, bilinear=False):
        super(up, self).__init__()

        if bilinear:
            self.up = nn.Upsample(scale_factor=2,
                                  mode='bilinear',
                                  align_corners=True)
        else:
            self.up = nn.ConvTranspose2d(in_ch, in_ch, 2, stride=2)

    def forward(self, x):
        x = self.up(x)
        return x


class ChannelAttention(nn.Module):
    def __init__(self, in_channels, ratio=16):
        super(ChannelAttention, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.fc1 = nn.Conv2d(in_channels, in_channels//ratio, 1, bias=False)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Conv2d(in_channels//ratio, in_channels,1, bias=False)
        self.sigmod = nn.Sigmoid()

    def forward(self,x):
        avg_out = self.fc2(self.relu1(self.fc1(self.avg_pool(x))))
        max_out = self.fc2(self.relu1(self.fc1(self.max_pool(x))))
        out = avg_out + max_out
        return self.sigmod(out)


class SNUNet_ECAM(nn.Module):
    # SNUNet-CD with ECAM
    def __init__(self, s1_in_ch=2, s2_in_ch=13, out_ch=2):
        super(SNUNet_ECAM, self).__init__()
        torch.nn.Module.dump_patches = True
        n1 = 32  # the initial number of channels of feature map
        filters = [n1, n1 * 2, n1 * 4, n1 * 8, n1 * 16]

        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

        self.conv0_0_S1 = Conv_Block_Nested(s1_in_ch, filters[0], filters[0])
        self.conv0_0_S2 = Conv_Block_Nested(s2_in_ch, filters[0], filters[0])

        self.conv1_0_S1 = Conv_Block_Nested(filters[0], filters[1], filters[1])
        self.conv1_0_S2 = Conv_Block_Nested(filters[0], filters[1], filters[1])
        self.Up1_0 = up(filters[1] * 2)

        self.conv2_0_S1 = Conv_Block_Nested(filters[1], filters[2], filters[2])
        self.conv2_0_S2 = Conv_Block_Nested(filters[1], filters[2], filters[2])
        self.Up2_0 = up(filters[2] * 2)

        self.conv3_0_S1 = Conv_Block_Nested(filters[2], filters[3], filters[3])
        self.conv3_0_S2 = Conv_Block_Nested(filters[2], filters[3], filters[3])
        self.Up3_0 = up(filters[3] * 2)

        self.conv4_0_S1 = Conv_Block_Nested(filters[3], filters[4], filters[4])
        self.conv4_0_S2 = Conv_Block_Nested(filters[3], filters[4], filters[4])
        self.Up4_0 = up(filters[4] * 2)

        self.conv0_1 = Conv_Block_Nested(filters[0] * 4 + filters[1] * 2, filters[0] * 2, filters[0] * 2)
        self.conv1_1 = Conv_Block_Nested(filters[1] * 4 + filters[2] * 2, filters[1] * 2, filters[1] * 2)
        self.Up1_1 = up(filters[1] * 2)
        self.conv2_1 = Conv_Block_Nested(filters[2] * 4 + filters[3] * 2, filters[2] * 2, filters[2] * 2)
        self.Up2_1 = up(filters[2] * 2)
        self.conv3_1 = Conv_Block_Nested(filters[3] * 4 + filters[4] * 2, filters[3] * 2, filters[3] * 2)
        self.Up3_1 = up(filters[3] * 2)

        self.conv0_2 = Conv_Block_Nested(filters[0] * 6 + filters[1] * 2, filters[0] * 2, filters[0] * 2)
        self.conv1_2 = Conv_Block_Nested(filters[1] * 6 + filters[2] * 2, filters[1] * 2, filters[1] * 2)
        self.Up1_2 = up(filters[1] * 2)
        self.conv2_2 = Conv_Block_Nested(filters[2] * 6 + filters[3] * 2, filters[2] * 2, filters[2] * 2)
        self.Up2_2 = up(filters[2] * 2)

        self.conv0_3 = Conv_Block_Nested(filters[0] * 8 + filters[1] * 2, filters[0] * 2, filters[0] * 2)
        self.conv1_3 = Conv_Block_Nested(filters[1] * 8 + filters[2] * 2, filters[1] * 2, filters[1] * 2)
        self.Up1_3 = up(filters[1] * 2)

        self.conv0_4 = Conv_Block_Nested(filters[0] * 10 + filters[1] * 2, filters[0] * 2, filters[0] * 2)

        self.ca = ChannelAttention(filters[0] * 8, ratio=16)
        self.ca1 = ChannelAttention(filters[0] * 2, ratio=16 // 4)

        self.conv_final = nn.Conv2d(filters[0] * 8, out_ch, kernel_size=1)
        self.sm = nn.LogSoftmax(dim=1)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, (nn.BatchNorm2d, nn.GroupNorm)):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, S2_A, S2_B, S1_A, S1_B):
        # S2 Image Stage
        '''S2_A'''
        S2_0_0A = self.conv0_0_S2(S2_A)                 #filters[0]
        S2_1_0A = self.conv1_0_S2(self.pool(S2_0_0A))   #filters[1]
        S2_2_0A = self.conv2_0_S2(self.pool(S2_1_0A))   #filters[2]
        S2_3_0A = self.conv3_0_S2(self.pool(S2_2_0A))   #filters[3]
        # S2_4_0A = self.conv4_0(self.pool(S2_3_0A))
        '''S2_B'''
        S2_0_0B = self.conv0_0_S2(S2_B)                 #filters[0]
        S2_1_0B = self.conv1_0_S2(self.pool(S2_0_0B))   #filters[1]
        S2_2_0B = self.conv2_0_S2(self.pool(S2_1_0B))   #filters[2]
        S2_3_0B = self.conv3_0_S2(self.pool(S2_2_0B))   #filters[3]
        S2_4_0B = self.conv4_0_S2(self.pool(S2_3_0B))   #filters[4]

        # S1 Image Stage
        '''S1_A'''
        S1_0_0A = self.conv0_0_S1(S1_A)                 #filters[0]
        S1_1_0A = self.conv1_0_S1(self.pool(S1_0_0A))   #filters[1]
        S1_2_0A = self.conv2_0_S1(self.pool(S1_1_0A))   #filters[2]
        S1_3_0A = self.conv3_0_S1(self.pool(S1_2_0A))   #filters[3]
        # S1_4_0A = self.conv4_0(self.pool(S1_3_0A))
        '''S1_B'''
        S1_0_0B = self.conv0_0_S1(S1_B)                 #filters[0]
        S1_1_0B = self.conv1_0_S1(self.pool(S1_0_0B))   #filters[1]
        S1_2_0B = self.conv2_0_S1(self.pool(S1_1_0B))   #filters[2]
        S1_3_0B = self.conv3_0_S1(self.pool(S1_2_0B))   #filters[3]
        S1_4_0B = self.conv4_0_S1(self.pool(S1_3_0B))   #filters[4]

        # Cat Stage
        x0_0A = torch.cat([S1_0_0A, S2_0_0A], 1)        #filters[0] * 2
        x0_0B = torch.cat([S1_0_0B, S2_0_0B], 1)        #filters[0] * 2

        x1_0A = torch.cat([S1_1_0A, S2_1_0A], 1)        #filters[1] * 2
        x1_0B = torch.cat([S1_1_0B, S2_1_0B], 1)        #filters[1] * 2

        x2_0A = torch.cat([S1_2_0A, S2_2_0A], 1)        #filters[2] * 2
        x2_0B = torch.cat([S1_2_0B, S2_2_0B], 1)        #filters[2] * 2

        x3_0A = torch.cat([S1_3_0A, S2_3_0A], 1)        #filters[3] * 2
        x3_0B = torch.cat([S1_3_0B, S2_3_0B], 1)        #filters[3] * 2

        # x4_0A = torch.cat([S1_4_0A, S2_4_0A], 1)
        x4_0B = torch.cat([S1_4_0B, S2_4_0B], 1)        #filters[4] * 2

        # Up Stage
        x0_1 = self.conv0_1(torch.cat([x0_0A, x0_0B, self.Up1_0(x1_0B)], 1))
        # filters[0] * 4 + filters[1] * 2 --> filters[0] * 2
        x1_1 = self.conv1_1(torch.cat([x1_0A, x1_0B, self.Up2_0(x2_0B)], 1))
        # filters[1] * 4 + filters[2] * 2 --> filters[1] * 2
        x0_2 = self.conv0_2(torch.cat([x0_0A, x0_0B, x0_1, self.Up1_1(x1_1)], 1))
        # filters[0] * 6 + filters[1] * 2 --> filters[0] * 2
        x2_1 = self.conv2_1(torch.cat([x2_0A, x2_0B, self.Up3_0(x3_0B)], 1))
        # filters[2] * 4 + filters[3] * 2 --> filters[2] * 2
        x1_2 = self.conv1_2(torch.cat([x1_0A, x1_0B, x1_1, self.Up2_1(x2_1)], 1))
        # filters[1] * 6 + filters[2] * 2 --> filters[1] * 2
        x0_3 = self.conv0_3(torch.cat([x0_0A, x0_0B, x0_1, x0_2, self.Up1_2(x1_2)], 1))
        # filters[0] * 8 + filters[1] * 2 --> filters[0] * 2

        x3_1 = self.conv3_1(torch.cat([x3_0A, x3_0B, self.Up4_0(x4_0B)], 1))
        # filters[3] * 4 + filters[4] * 2 --> filters[3] * 2
        x2_2 = self.conv2_2(torch.cat([x2_0A, x2_0B, x2_1, self.Up3_1(x3_1)], 1))
        # filters[2] * 6 + filters[3] * 2 --> filters[2] * 2
        x1_3 = self.conv1_3(torch.cat([x1_0A, x1_0B, x1_1, x1_2, self.Up2_2(x2_2)], 1))
        # filters[1] * 8 +  filters[2] * 2 --> filters[1] * 2
        x0_4 = self.conv0_4(torch.cat([x0_0A, x0_0B, x0_1, x0_2, x0_3, self.Up1_3(x1_3)], 1))
        # filters[0] * 10 + filters[1] * 2  --> filters[0] * 2

        out = torch.cat([x0_1, x0_2, x0_3, x0_4], 1)
        # filters[0] * 8

        intra = torch.sum(torch.stack((x0_1, x0_2, x0_3, x0_4)), dim=0)
        ca1 = self.ca1(intra)
        out = self.ca(out) * (out + ca1.repeat(1, 4, 1, 1)) #@TODO is this should be modified?
        out = self.conv_final(out)
        out = self.sm(out)

        return out
