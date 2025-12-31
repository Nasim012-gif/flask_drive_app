import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, Button, TouchableOpacity, Alert } from 'react-native';
import { Camera } from 'expo-camera';
import { BarCodeScanner } from 'expo-barcode-scanner';
import { WebView } from 'react-native-webview';
import { StatusBar } from 'expo-status-bar';

export default function App() {
    const [hasPermission, setHasPermission] = useState(null);
    const [scanned, setScanned] = useState(false);
    const [currentUrl, setCurrentUrl] = useState('https://nasim-event-app-2025.onrender.com'); // Default to home
    const [showScanner, setShowScanner] = useState(false);

    useEffect(() => {
        const getBarCodeScannerPermissions = async () => {
            const { status } = await Camera.requestCameraPermissionsAsync();
            setHasPermission(status === 'granted');
        };

        getBarCodeScannerPermissions();
    }, []);

    const handleBarCodeScanned = ({ type, data }) => {
        setScanned(true);
        setShowScanner(false);

        // Check if it's a valid GetPhotos URL
        if (data.includes('nasim-event-app-2025.onrender.com')) {
            setCurrentUrl(data);
            Alert.alert('Event Found!', 'Loading your event...');
        } else {
            Alert.alert('Invalid QR Code', 'This does not look like a GetPhotos event code.');
        }
    };

    if (hasPermission === null) {
        return <View style={styles.container}><Text>Requesting for camera permission</Text></View>;
    }
    if (hasPermission === false) {
        return <View style={styles.container}><Text>No access to camera</Text></View>;
    }

    // Scanner View
    if (showScanner) {
        return (
            <View style={styles.container}>
                <Camera
                    style={StyleSheet.absoluteFillObject}
                    barCodeScannerSettings={{
                        barCodeTypes: [BarCodeScanner.Constants.BarCodeType.qr],
                    }}
                    onBarCodeScanned={scanned ? undefined : handleBarCodeScanned}
                />
                <View style={styles.overlay}>
                    <Text style={styles.scanText}>San Event QR Code</Text>
                    <TouchableOpacity style={styles.cancelBtn} onPress={() => setShowScanner(false)}>
                        <Text style={styles.btnText}>Cancel</Text>
                    </TouchableOpacity>
                </View>
                <StatusBar style="light" />
            </View>
        );
    }

    // WebView (Main App)
    return (
        <View style={styles.container}>
            <WebView
                source={{ uri: currentUrl }}
                style={styles.webview}
                marginTop={30}
            />

            {/* Native Navigation Bar */}
            <View style={styles.navBar}>
                <TouchableOpacity style={styles.navBtn} onPress={() => setCurrentUrl('https://nasim-event-app-2025.onrender.com/admin')}>
                    <Text style={styles.navText}>Admin Login</Text>
                </TouchableOpacity>

                <TouchableOpacity style={styles.scanBtn} onPress={() => {
                    setScanned(false);
                    setShowScanner(true);
                }}>
                    <Text style={styles.scanBtnText}>📸 Scan QR</Text>
                </TouchableOpacity>

                <TouchableOpacity style={styles.navBtn} onPress={() => setCurrentUrl('https://nasim-event-app-2025.onrender.com')}>
                    <Text style={styles.navText}>Home</Text>
                </TouchableOpacity>
            </View>
            <StatusBar style="auto" />
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#fff',
    },
    webview: {
        flex: 1,
    },
    overlay: {
        position: 'absolute',
        bottom: 50,
        left: 0,
        right: 0,
        alignItems: 'center',
    },
    scanText: {
        color: 'white',
        fontSize: 20,
        fontWeight: 'bold',
        marginBottom: 20,
        backgroundColor: 'rgba(0,0,0,0.5)',
        padding: 10,
        borderRadius: 5,
    },
    cancelBtn: {
        backgroundColor: 'white',
        padding: 15,
        borderRadius: 30,
        width: 120,
        alignItems: 'center',
    },
    btnText: {
        color: 'black',
        fontWeight: 'bold',
    },
    navBar: {
        flexDirection: 'row',
        justifyContent: 'space-around',
        alignItems: 'center',
        paddingBottom: 20,
        paddingTop: 10,
        backgroundColor: '#f8f9fa',
        borderTopWidth: 1,
        borderTopColor: '#e9ecef',
    },
    navBtn: {
        padding: 10,
    },
    navText: {
        color: '#6c757d',
        fontWeight: '600',
    },
    scanBtn: {
        backgroundColor: '#667eea',
        paddingVertical: 10,
        paddingHorizontal: 20,
        borderRadius: 25,
        top: -15,
        shadowColor: "#000",
        shadowOffset: {
            width: 0,
            height: 4,
        },
        shadowOpacity: 0.30,
        shadowRadius: 4.65,
        elevation: 8,
    },
    scanBtnText: {
        color: 'white',
        fontWeight: 'bold',
        fontSize: 16,
    },
});
